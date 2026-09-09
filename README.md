# C4D Scripts

用于集中存放 Cinema 4D 相关脚本、插件与 Python 标签代码。

## 开发基准

本项目所有开发默认以 **Cinema 4D 2025 版 API** 为基准。

- 脚本、插件与 Python Tag 默认优先兼容 Cinema 4D 2025。
- API、常量、对象类型、事件与行为均以 Cinema 4D 2025 的实现为主要参考。
- 如需兼容其他 Cinema 4D 版本，应在具体任务中单独说明，并尽量避免影响 2025 版的默认行为。

## 仓库结构

本仓库按任务类型进行归档。目前至少分为以下三类：

```text
C4D_Scripts/
├─ scripts/       # Cinema 4D 内直接运行的脚本
├─ plugins/       # Cinema 4D 插件
├─ python_tags/   # Cinema 4D Python 标签脚本
└─ README.md
```

### `scripts/`

存放可在 Cinema 4D 脚本管理器中直接运行的脚本，例如对象处理、批量操作、动画辅助、建模辅助等工具。

### `plugins/`

存放需要以 Cinema 4D 插件形式安装和运行的功能，包括具有独立界面、持续状态或更复杂集成功能的工具。

### `python_tags/`

存放用于 Cinema 4D Python Tag 的代码，适合依附于场景对象、随场景运行或根据对象状态实时执行的逻辑。

## 归档规则

新增内容时，根据实际用途放入对应目录：

- 普通 C4D 脚本 → `scripts/`
- C4D 插件 → `plugins/`
- Python 标签代码 → `python_tags/`

后续如出现新的明确任务类型，可继续增加新的一级目录，例如资源、示例、文档等；不强行塞入现有三类。
