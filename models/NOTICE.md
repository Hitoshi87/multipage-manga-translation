# Optional balloon model

Original weights: [huyvux3005/manga109-segmentation-bubble](https://huggingface.co/huyvux3005/manga109-segmentation-bubble), model card declares Apache-2.0, single-class YOLO11n instance segmentation. The publisher reports training on Manga109/MangaSegmentation. Those reports are not this project's measured accuracy.

ONNX export (fixed 1600 square): [igun997/manga-translator](https://github.com/igun997/manga-translator/tree/1397af38e3464cdf4931c705857b8bef015030dc/manga_models). Exporter declares no changes to weights. The export is downloaded separately; it is not committed or redistributed with this source tree.

Export SHA-256: `88b84105ad2faec516fd164a2783fa6b6007dfd6ab07aa90e92b0241e51ea4cf`, 12,465,247 bytes. Inference uses ONNX Runtime only. No Ultralytics/PyTorch runtime or external image service. See the original model/exporter licenses before redistribution. This model predicts balloons, not faces or character-level text masks; independent cleaning safeguards and review remain necessary.

# Optional comic text detector

[ogkalu/comic-text-and-bubble-detector](https://huggingface.co/ogkalu/comic-text-and-bubble-detector), model card declares Apache-2.0. The int8 ONNX file is downloaded separately at revision `16e8a622f91fabc6b5b65c96d32d1183f8843546`; SHA-256 `b5022ad46416b6fe4f88b0cc082cfd2ff5b1cfc624088c2f19879485493f5913`, 43,838,857 bytes. It supplies text bounding boxes, not pixel masks. Unmatched boxes are review-only and never authorize erasing artwork.

# Optional preview models

The setup script downloads individually pinned weights, verifies SHA-256 and does not commit weights. Preview runs locally. [Comic Text Detector ONNX](https://huggingface.co/lemondouble/lemon-manga-translator) is distributed as GPL-3.0. [Comic Text Mask](https://huggingface.co/TareHimself/comic-text-mask) declares MIT. [LaMa Manga ONNX](https://huggingface.co/ogkalu/lama-manga-onnx-dynamic) is based on the manga inpainting model; consult the model and upstream licenses before distribution. These masks may include drawing pixels and the previews are not automatically applied to chapter output.

[Koharu Layout 1152 ONNX](https://huggingface.co/ShiniShiho/koharu-layout-rfdetr-seg-2xl-1152-onnx) is an export of [mayocream's original model](https://huggingface.co/mayocream/koharu-layout-rfdetr-seg-2xl-1152). The publisher specifies a custom license and conditions connected to Manga109 academic-use data; check the model card and data terms before use. This is the 1152 model, not the newer Koharu-only HighRes model.

# Optional assistance models

- [AnimeHeads v3 ONNX](https://huggingface.co/tori29umai/AnimeHeads-ONNX), derived from [AnimeHeads](https://huggingface.co/nyuuzyou/AnimeHeads), supplies approximate head boxes, not face segmentation. Its model can miss heads and leave text near detected heads uncleaned.
- [Baberu OCR](https://huggingface.co/genshiai-daichi/baberu-ocr), Apache-2.0. The local ONNX implementation follows the author's published `onnx_infer.py`.
- [multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small), MIT; outputs semantic similarity, not calibrated probabilities.
- [Magi](https://huggingface.co/ragavsachdeva/magi) is distributed for personal, research, non-commercial and not-for-profit use; other uses require contacting the author. The pinned upstream inference code is used locally with OCR disabled.
- [Qwen2.5-VL-3B-Instruct 4-bit MLX](https://huggingface.co/mlx-community/Qwen2.5-VL-3B-Instruct-4bit) supplies optional font-role suggestions on the local Mac. Check upstream model and distribution terms.

# AOT Koharu alternative (2026-11-06)

[mayocream/aot-inpainting](https://huggingface.co/mayocream/aot-inpainting), revision `cffe2346ac2b5ebe1f2d61335d602d12cc144c6f`, declares MIT. SafeTensors file `models/aot_manga.safetensors`: 22,732,864 bytes, SHA-256 `1b4fea17a84a228c2097a42ab2f403357f07bb56ae022dc243b40817b7aa87d1`, 5,679,244 parameters. Architecture compatible with [zyddnys/manga-image-translator AOTGenerator](https://github.com/zyddnys/manga-image-translator/blob/main/manga_translator/inpainting/inpainting_aot.py); see upstream licensing before redistribution. Local implementation reads only verified SafeTensors, never executes downloaded model code. LaMa/AOT inference is crop-local; neither repairs an incorrect detection mask automatically.
