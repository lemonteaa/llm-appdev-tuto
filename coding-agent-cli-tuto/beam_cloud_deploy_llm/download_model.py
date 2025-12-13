from beam import function, Volume, Image

VOLUME_PATH = "/app/models"

MODEL_ID = "unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF"
MODEL_FILE = "Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf"

image = Image().add_python_packages(["huggingface_hub", "pypdl"])

@function(
    volumes=[Volume(name="huggingface_models", mount_path=VOLUME_PATH)],
    image=image,
    headless=True,
)
def load_model():
    #from huggingface_hub import hf_hub_download
    #print("Begin download")
    #res = hf_hub_download(repo_id=MODEL_ID, filename=MODEL_FILE, local_dir=f"{VOLUME_PATH}/{MODEL_ID}/")
    #print(res)
    from pypdl import Pypdl
    dl = Pypdl(max_concurrent=5)
    print("start")
    dl.start(url="https://huggingface.co/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF/resolve/main/Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf", file_path=f"{VOLUME_PATH}/{MODEL_ID}/{MODEL_FILE}")
    print("done!")

if __name__ == "__main__":
    load_model.remote()

