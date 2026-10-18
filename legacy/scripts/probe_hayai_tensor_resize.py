"""One-variable local Hayai resize comparison, NEVER a runtime backend.

Keep PIL-processor geometry, normalization, patches, model and generation fixed.
Only RGB uint8 resizing changes to the tensor bilinear/antialias recipe. This
does not establish torchvision/Fast parity: no torchvision runtime is present.
Images remain in RAM; existing comparator checksum/offline guards still apply.
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "companion")]
from benchmark_hayai_nova import HayaiRecognizer, offline_guard, run


def target_size(height, width, patches):
    from transformers.models.siglip2.image_processing_siglip2 import get_image_size_for_max_num_patches
    return get_image_size_for_max_num_patches(height, width, 16, patches)


def tensor_resize(image, height, width):
    """CPU RGB uint8 -> antialiased bilinear -> RGB uint8; never crop/rotate.

    The tensor comes from HWC PIL storage (CHW stride(0)==1), as pil_to_tensor
    does. Preserve that memory layout for the native uint8 interpolation route.
    No weights, source text, punctuation, files, downloads or network here.
    """
    from PIL import Image
    if (not isinstance(image, Image.Image) or image.mode != "RGB"
            or any(type(v) is not int or not 1 <= v <= 8192 for v in (height, width))
            or height * width > 512 * 16 * 16):
        raise ValueError("Bounded RGB uint8 tensor resize required")
    import numpy as np
    import torch
    pixels = torch.from_numpy(np.array(image, dtype=np.uint8, copy=True)).permute(2, 0, 1).unsqueeze(0)
    # torchvision's tensor kernel repairs the ambiguous singleton batch
    # stride for HWC-derived CHW storage before native uint8 interpolation.
    # This is still a diagnostic subset, not a substitute for Fast parity QA.
    if pixels.is_contiguous(memory_format=torch.channels_last):
        pixels = pixels.as_strided(pixels.shape, (pixels.numel(), *pixels.stride()[1:]))
    if pixels.shape[-2:] != (height, width):
        pixels = torch.nn.functional.interpolate(pixels, size=(height, width), mode="bilinear",
                                                align_corners=False, antialias=True)
    if pixels.dtype != torch.uint8 or pixels.device.type != "cpu":
        raise ValueError("Resize changed fixed CPU/uint8 contract")
    return Image.fromarray(pixels[0].permute(1, 2, 0).numpy())


class TensorResizeProcessor:
    """Ablate only resize, delegating all later processing to the same PIL class."""
    def __init__(self, slow, audit_pairs=False):
        self.slow = slow
        self.audit_pairs = audit_pairs
        self.pairs = []

    def __call__(self, *, images, max_num_patches, return_tensors):
        from PIL import Image
        if (not isinstance(images, list) or len(images) != 1
                or not isinstance(images[0], Image.Image) or images[0].mode != "RGB"
                or type(max_num_patches) is not int or max_num_patches not in (256, 384, 512)
                or return_tensors != "pt"):
            raise ValueError("Fixed single RGB crop/patch/tensor contract required")
        image = images[0]
        height, width = target_size(image.height, image.width, max_num_patches)
        resized = tensor_resize(image, height, width)
        result = self.slow(images=[resized], max_num_patches=max_num_patches,
                           return_tensors=return_tensors, do_resize=False)
        if self.audit_pairs:
            import torch
            baseline = self.slow(images=images, max_num_patches=max_num_patches, return_tensors=return_tensors)
            for key in ("pixel_attention_mask", "spatial_shapes"):
                if not torch.equal(result[key], baseline[key]):
                    raise ValueError("Resize comparison changed mask/spatial geometry")
            pixels, reference = result["pixel_values"], baseline["pixel_values"]
            valid = int(result["pixel_attention_mask"].sum())
            if (pixels.shape != reference.shape or pixels.dtype != torch.float32
                    or not torch.isfinite(pixels).all()
                    or torch.count_nonzero(pixels[:, valid:]).item()):
                raise ValueError("Resize comparison changed pixel shape/dtype/padding")
            difference = (pixels[:, :valid] - reference[:, :valid]).abs()
            self.pairs.append({"source_size": list(image.size), "target_size": [width, height],
                               "valid_patches": valid, "geometry_mask_equal": True,
                               "max_abs": float(difference.max()), "mean_abs": float(difference.mean()),
                               "different_values": int(torch.count_nonzero(difference)),
                               "values_above_1e_minus_6": int(torch.count_nonzero(difference > 1e-6))})
        return result


class TensorResizeHayaiRecognizer(HayaiRecognizer):
    def __init__(self, patches=512, threads=4):
        super().__init__(patches, threads)
        self.name += "-tensor-resize-only"
        self.details.update(image_processor="Siglip2-PIL-with-torch-uint8-resize-only",
                            processor_upstream_parity=False,
                            experimental_field="resize kernel only; slow normalization/patches unchanged")

    def load(self):
        if self.model is not None:
            return
        super().load()
        self.processor = TensorResizeProcessor(self.processor, audit_pairs=True)
        self.details["resize_tensor_checks"] = self.processor.pairs
        import torch
        self.details.update(torch_version=torch.__version__,
                            cpu_capability=torch.backends.cpu.get_cpu_capability(),
                            tensor_resize_recipe="CPU uint8 eager bilinear/antialias; not verified Fast")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--authored", action="store_true")
    source.add_argument("--folder")
    parser.add_argument("--full-pages", action="store_true")
    parser.add_argument("--patches", type=int, choices=(256, 384, 512), default=512)
    parser.add_argument("--threads", type=int, choices=range(1, 9), default=4)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    with offline_guard() as attempts:
        args.socket_attempts = attempts
        run(args, engine_override=TensorResizeHayaiRecognizer(args.patches, args.threads))
        if attempts:
            raise RuntimeError("Resize comparison attempted network I/O; reject offline gate")
