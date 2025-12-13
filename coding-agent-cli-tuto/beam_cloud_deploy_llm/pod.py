from beam import Image, Pod, Volume

VOLUME_PATH = "/app/models"

MODEL_ID = "unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF"

MODEL_FILE = "Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf"

#docker pull ghcr.io/ggml-org/llama.cpp:server-cuda-b7293

pod = Pod(
    name="llamacpp-infer-qwen3-coder-30b-a3b-instruct-unsloth",
    ports=[8329],
    cpu=1,
    memory="2Gi",
    gpu="RTX4090",
    image=Image.from_registry("ghcr.io/ggml-org/llama.cpp:server-cuda-b7293"),
    volumes=[Volume(name="huggingface_models", mount_path=VOLUME_PATH)],
    keep_warm_seconds=300,  # 5 minutes idle timeout
    entrypoint=[
        "/app/llama-server",
        "-m", f"{VOLUME_PATH}/{MODEL_ID}/{MODEL_FILE}",
        "--host", "0.0.0.0",
        "--port", "8329",
        "-c", "88000",
        "--no-mmap",
        "--jinja",
        "--temp", "0.7", 
        "--top-k", "20",
        "--top-p", "0.8",
        "--repeat-penalty", "1.05",
        "-ncmoe", "0",
        "--cache-type-k", "q8_0",
        "--cache-type-v", "q8_0",
    ]
)

