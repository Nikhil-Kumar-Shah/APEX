"""Hugging Face Transformers inference engine adapter."""

import gc
import sys
import logging
from typing import Any, Dict, Generator, Optional

from runtime.core.errors import EngineUnavailableError, GPUNotFoundError, GPUOutOfMemoryError
from runtime.engine.base import BaseInferenceEngine

logger = logging.getLogger("runtime.engine.transformers")


class TransformersInferenceEngine(BaseInferenceEngine):
    """Adapter for the Hugging Face Transformers library."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.model = None
        self.tokenizer = None
        self.device = "cpu"

    def _verify_dependencies(self) -> None:
        """Verifies that PyTorch and Transformers are installed."""
        try:
            import torch
            import transformers
        except ImportError as e:
            raise EngineUnavailableError(
                "transformers",
                details=f"Missing libraries: {e}",
            )

    def load_model(self, model_path: str, parameters: Optional[Dict[str, Any]] = None) -> None:
        self._verify_dependencies()
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        params = parameters or {}
        req_device = params.get("device")
        if req_device:
            dev_str = str(req_device).lower().strip()
            if dev_str.startswith("cuda"):
                if not torch.cuda.is_available():
                    raise GPUNotFoundError(
                        f"Device '{req_device}' was explicitly requested, but CUDA is not available in the current runtime."
                    )
                self.device = "cuda"
            elif dev_str == "cpu":
                self.device = "cpu"
            else:
                self.device = str(req_device)
        else:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Determine precision and device mappings
        torch_dtype = torch.float16 if self.device == "cuda" else torch.float32
        precision = params.get("precision", "float16")
        if precision == "bfloat16" and self.device == "cuda":
            if hasattr(torch.cuda, "is_bf16_supported") and torch.cuda.is_bf16_supported():
                torch_dtype = torch.bfloat16
        elif precision == "float32":
            torch_dtype = torch.float32

        hf_token = params.get("hf_token")
        try:
            tok_kwargs = {"trust_remote_code": True}
            if hf_token:
                tok_kwargs["token"] = hf_token
            self.tokenizer = AutoTokenizer.from_pretrained(model_path, **tok_kwargs)

            # Defensive loading against OOM
            load_kwargs = {
                "torch_dtype": torch_dtype,
                "low_cpu_mem_usage": True,
                "trust_remote_code": True,
            }
            if hf_token:
                load_kwargs["token"] = hf_token

            # Support 4-bit / 8-bit quantization if requested and available
            if precision in ("4bit", "int4", "4-bit"):
                try:
                    from transformers import BitsAndBytesConfig
                    load_kwargs["quantization_config"] = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=torch_dtype,
                    )
                except Exception as bnb_err:
                    logger.warning(f"BitsAndBytes 4-bit unavailable ({bnb_err}); falling back to standard precision.")
            elif precision in ("8bit", "int8", "8-bit"):
                try:
                    from transformers import BitsAndBytesConfig
                    load_kwargs["quantization_config"] = BitsAndBytesConfig(
                        load_in_8bit=True,
                    )
                except Exception as bnb_err:
                    logger.warning(f"BitsAndBytes 8-bit unavailable ({bnb_err}); falling back to standard precision.")

            if self.device == "cuda":
                load_kwargs["device_map"] = "auto"

            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                **load_kwargs
            )
            self.current_model_id = model_path
            self.is_loaded = True
        except (RuntimeError, Exception) as e:
            err_str = str(e).lower()
            if "out of memory" in err_str or "cuda error: out of memory" in err_str:
                raise GPUOutOfMemoryError(log_info={"error": str(e)})
            raise e

    def unload_model(self) -> None:
        self.model = None
        self.tokenizer = None
        self.current_model_id = None
        self.is_loaded = False

        # Run garbage collection and empty CUDA cache
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    def generate_stream(
        self,
        prompt: Any,
        generation_params: Optional[Dict[str, Any]] = None,
    ) -> Generator[str, None, None]:
        if not self.is_loaded or self.model is None or self.tokenizer is None:
            raise RuntimeError("Model is not loaded.")

        import torch
        from transformers import TextIteratorStreamer
        from threading import Thread

        # Prepare parameters
        g_params = generation_params or {}
        max_new_tokens = g_params.get("max_new_tokens", 512)
        temperature = g_params.get("temperature", 0.7)
        top_p = g_params.get("top_p", 0.9)

        inputs = None
        if isinstance(prompt, list):
            if hasattr(self.tokenizer, "apply_chat_template"):
                try:
                    tensor_inputs = self.tokenizer.apply_chat_template(
                        prompt,
                        return_tensors="pt",
                        add_generation_prompt=True
                    ).to(self.device)
                    attention_mask = torch.ones_like(tensor_inputs).to(self.device)
                    inputs = {"input_ids": tensor_inputs, "attention_mask": attention_mask}
                except Exception as err:
                    logger.warning(f"apply_chat_template failed: {err}")
                    inputs = None
            if inputs is None:
                str_prompt = ""
                for m in prompt:
                    r = m.get("role", "user") if isinstance(m, dict) else getattr(m, "role", "user")
                    c = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
                    str_prompt += f"<|im_start|>{r}\n{c}<|im_end|>\n"
                str_prompt += "<|im_start|>assistant\n"
                enc = self.tokenizer(str_prompt, return_tensors="pt").to(self.device)
                inputs = {"input_ids": enc.input_ids, "attention_mask": enc.attention_mask}
        elif isinstance(prompt, str):
            enc = self.tokenizer(prompt, return_tensors="pt").to(self.device)
            inputs = {"input_ids": enc.input_ids, "attention_mask": enc.attention_mask}
        else:
            enc = self.tokenizer(str(prompt), return_tensors="pt").to(self.device)
            inputs = {"input_ids": enc.input_ids, "attention_mask": enc.attention_mask}

        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)

        from transformers import StoppingCriteria, StoppingCriteriaList

        class StopOnTokensCriteria(StoppingCriteria):
            def __init__(self, stop_ids):
                super().__init__()
                self.stop_ids = set(stop_ids)

            def __call__(self, input_ids: Any, scores: Any, **kwargs) -> bool:
                for seq in input_ids:
                    if len(seq) > 0 and seq[-1].item() in self.stop_ids:
                        return True
                return False

        eos_ids = set()
        if hasattr(self.tokenizer, "eos_token_id") and self.tokenizer.eos_token_id is not None:
            if isinstance(self.tokenizer.eos_token_id, list):
                eos_ids.update([t for t in self.tokenizer.eos_token_id if isinstance(t, int)])
            elif isinstance(self.tokenizer.eos_token_id, int):
                eos_ids.add(self.tokenizer.eos_token_id)

        for stop_sym in ["<|im_end|>", "<|endoftext|>", "<|im_start|>", "<|eot_id|>", "<end_of_turn>", "</s>", "<eos>"]:
            try:
                t_id = self.tokenizer.convert_tokens_to_ids(stop_sym)
                if t_id is not None and isinstance(t_id, int) and t_id > 0:
                    eos_ids.add(t_id)
            except Exception:
                pass

        stopping_criteria = StoppingCriteriaList([StopOnTokensCriteria(list(eos_ids))]) if eos_ids else None

        pad_token_id = getattr(self.tokenizer, "pad_token_id", None)
        if pad_token_id is None and eos_ids:
            pad_token_id = next(iter(eos_ids))

        generation_kwargs = dict(
            **inputs,
            streamer=streamer,
            max_new_tokens=max_new_tokens,
            pad_token_id=pad_token_id,
            eos_token_id=list(eos_ids) if eos_ids else None,
            repetition_penalty=1.1,
        )
        if stopping_criteria:
            generation_kwargs["stopping_criteria"] = stopping_criteria

        if temperature > 0.0:
            generation_kwargs["do_sample"] = True
            generation_kwargs["temperature"] = temperature
            generation_kwargs["top_p"] = top_p
        else:
            generation_kwargs["do_sample"] = False

        generation_errors = []

        def _run_generation():
            try:
                self.model.generate(**generation_kwargs)
            except Exception as e:
                logger.error(f"Error in model.generate: {e}", exc_info=True)
                generation_errors.append(e)

        # Run model generation in a background thread to allow streamer consumption
        thread = Thread(target=_run_generation, daemon=True)
        thread.start()

        stop_words = [
            "<|im_end|>", "<|endoftext|>", "<|im_start|>",
            "<|eot_id|>", "<end_of_turn>", "</s>", "<eos>",
            "\n<|im_start|>", "\n<|im_end|>",
            "\nuser\n", "\nUser:\n", "\nuser:\n",
            "\nassistant\n", "\nAssistant:\n",
        ]
        max_stop_len = max(len(sw) for sw in stop_words)

        tokens_yielded = 0
        buffer = ""
        should_stop = False

        try:
            for new_text in streamer:
                buffer += new_text

                # Check if buffer contains any complete stop word
                for sw in stop_words:
                    if sw in buffer:
                        buffer = buffer.split(sw)[0]
                        should_stop = True
                        break

                if should_stop:
                    if buffer:
                        tokens_yielded += 1
                        yield buffer
                    buffer = ""
                    break

                # If buffer is long enough, yield the safe prefix and retain potential partial matches
                if len(buffer) > max_stop_len:
                    safe_len = len(buffer) - max_stop_len
                    chunk_to_yield = buffer[:safe_len]
                    buffer = buffer[safe_len:]
                    if chunk_to_yield:
                        tokens_yielded += 1
                        yield chunk_to_yield

            # Flush any remaining clean buffer text at the end of generation
            if buffer and not should_stop:
                for sw in stop_words:
                    if sw in buffer:
                        buffer = buffer.split(sw)[0]
                if buffer:
                    tokens_yielded += 1
                    yield buffer
        finally:
            thread.join()
            if tokens_yielded == 0 and generation_errors:
                raise generation_errors[0]

    def get_status(self) -> Dict[str, Any]:
        status = {
            "engine": "transformers",
            "model": self.current_model_id,
            "is_ready": self.is_loaded,
            "device": self.device,
        }
        if self.device == "cuda":
            try:
                import torch

                status["vram_allocated_mb"] = torch.cuda.memory_allocated() / (1024 * 1024)
                status["vram_reserved_mb"] = torch.cuda.memory_reserved() / (1024 * 1024)
            except (ImportError, Exception):
                pass
        return status

    def is_compatible(self, model_path: str) -> bool:
        # Check standard config file naming
        from pathlib import Path

        path = Path(model_path)
        if path.is_dir():
            return (path / "config.json").exists()
        return True  # Remote HF repos are assumed compatible until checked
