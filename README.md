# Course Recording to Lecture Doc

一个可迁移的 Aime Skill：把课程录播、课件和板书关键帧整理成结构化飞书课程笔记。

与只提取音频的流程相比，它保留原视频作为视觉信息源，自动生成板书/课堂演示候选帧，再通过视觉复核选择完成态截图，并按时间戳插入对应知识点。

## 功能

- 从录播视频提取适合语音转写的单声道音频。
- 保守清理 SRT、VTT 或纯文本逐字稿。
- 将 PDF 课件渲染为逐页图片。
- 对视频定时采样，通过画面变化生成板书候选帧。
- 检测稳定的 PPT、动画完成态和现场演示镜头，并生成带编号、时间戳的联系表供人工复核。
- 支持用 ROI 只分析黑板区域，降低 PPT 翻页和人物走动误报。
- 指导 Agent 对齐逐字稿、课件、板书和演示时间戳，以图文左右或多图分栏生成飞书笔记。
- 非中文课程可整理成中文笔记，并保留术语、公式、代码和时间信息。

## 安装

将整个仓库复制或克隆到 Aime 工作区的 `user_skills/course-recording-to-lecture-doc/`：

```bash
git clone https://github.com/huqiongyin2-ops/course-recording-to-lecture-doc.git \
  user_skills/course-recording-to-lecture-doc
```

如从 GitHub 下载 ZIP，请确保解压后的目录名为 `course-recording-to-lecture-doc`，并保留根目录下的 `.skillignore`。

## 运行依赖

- Python 3.10+
- `ffmpeg`（包含 `ffprobe`）
- Python 包：`Pillow`、`PyMuPDF`
- Aime 中可用的 `lark-minutes`、`lark-doc`、`lark-shared` Skill（用于飞书转写与文档写入）

macOS 示例：

```bash
brew install ffmpeg
python3 -m pip install Pillow PyMuPDF
```

也可在仓库根目录运行：

```bash
python3 -m pip install -r requirements.txt
```

## 验证

在 Aime 环境中运行：

```bash
python3 /path/to/aime-skill-creator/scripts/quick_validate.py \
  user_skills/course-recording-to-lecture-doc
```

各脚本均支持 `--help`。完整工作流和参数说明见 [SKILL.md](SKILL.md)，板书筛选准则见 [references/visual-preservation.md](references/visual-preservation.md)，图文排版见 [references/lecture-doc-layout.md](references/lecture-doc-layout.md)。

稳定镜头检测、联系表复核和图文布局思路来自 `event-video-recap` 1.0.0，并于 2026-10-14 按课程场景改写；本仓库不依赖其安装目录、示例数据或内部脚本。

## 隐私提示

课程录播可能包含学生人脸、姓名、课堂对话或受版权保护的课件。上传、共享或发布生成文档前，请确认已获得相应权限；不要把录播、音频、逐字稿或候选截图提交到本仓库。

## License

MIT
