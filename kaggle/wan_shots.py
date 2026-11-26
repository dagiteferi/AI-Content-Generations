"""Wan 2.2 TI2V-5B image-to-video for every job in jobs.json.

Kaggle: GPU T4 x2, internet on.
    !pip install -q -U "diffusers>=0.43" transformers accelerate ftfy imageio imageio-ffmpeg
    !python /kaggle/input/<bundle>/wan_shots.py
"""

from pathlib import Path

import torch
from diffusers import AutoencoderKLWan, WanImageToVideoPipeline
from diffusers.utils import export_to_video, load_image
from PIL import ImageOps

from runner import Job, run_jobs

MODEL_ID = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"


def load_pipeline() -> WanImageToVideoPipeline:
    # T4 (compute 7.5) "supports" bf16 only by slow emulation, so use fp16 below compute 8.0.
    dtype = torch.bfloat16 if torch.cuda.get_device_capability()[0] >= 8 else torch.float16
    vae = AutoencoderKLWan.from_pretrained(MODEL_ID, subfolder="vae", torch_dtype=torch.float32)
    pipeline = WanImageToVideoPipeline.from_pretrained(MODEL_ID, vae=vae, torch_dtype=dtype)
    pipeline.enable_model_cpu_offload()
    return pipeline


PIPELINE = load_pipeline()


def generate(job: Job, bundle: Path, output: Path) -> None:
    image = ImageOps.fit(load_image(str(bundle / job["image"])), (job["width"], job["height"]))
    frames = PIPELINE(
        image=image,
        prompt=job["prompt"],
        negative_prompt=job["negative_prompt"],
        width=job["width"],
        height=job["height"],
        num_frames=job["frames"],
        guidance_scale=job["guidance"],
        num_inference_steps=job["steps"],
        generator=torch.Generator(device="cpu").manual_seed(job["seed"]),
    ).frames[0]
    export_to_video(frames, str(output), fps=job["fps"])


if __name__ == "__main__":
    run_jobs(generate)
