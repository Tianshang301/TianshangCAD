# TianshangCAD（cad-mcp-server）

一个现代化的 **CAD CLI + MCP Server** 系统。二维/三维绘图、编辑、测量、
校验以及 JSON 驱动的工作流，既可通过命令行使用，也可以作为标准化工具被任何
MCP 客户端（AI 智能体）直接调用。

> **当前状态**：Phase 1（CLI + IO）、Phase 2（MCP Server）、Phase 3（批处理
> 与自动化）与 Phase 4（高级功能）已完成。388 个测试通过，覆盖率 85%+，
> `ruff` 与 `mypy` 全部通过。

**English**: [README.md](../README.md)

## 功能特性

- **CAD CLI** — `file`、`draw`、`edit`、`view`、`measure`、`layer`、`batch`
  等命令组，支持短命令别名（`l` = `draw line`、`c` = `draw circle` ……）
- **MCP Server** — 47 个 JSON-RPC 工具，支持 stdio 与 streamable HTTP 两种
  传输方式，可供 Claude、Cursor 等 MCP 客户端调用
- **批处理与自动化** — 一次性 / Cron / 依赖链任务调度、沙箱化 Python / SCR /
  batch 脚本执行、Webhook 通知、SQLite 持久化与可复用的 Jinja2 命令模板
- **几何校验** — 自相交、退化面、非流形边检测，错误附带结构化的 `type` /
  `location` / `fix_suggestion`；box-box 干涉体积与拓扑统计
- **渲染** — 2D 正交投影 PNG（俯视 / 前视 / 侧视，DPI 72–300）、3D 着色预览
  与 Three.js WebGL 导出（含浏览器查看器）
- **版本管理** — 基于 `deepdiff` 的文档快照 保存 / 列表 / 对比 / 恢复
- **自然语言** — `cad_nlp_command` 将中英文请求映射为工具调用，并支持歧义澄清
- **JSON 驱动** — 场景与几何对象通过 Pydantic Schema 定义和校验，支持完整的
  导入/导出往返
- **可插拔内核** — 解析内核（默认，无原生依赖）/ OCC（`cadquery`）/ FreeCAD
- **文件 IO** — JSON、DXF、STL（STEP 依赖 OCC 内核）
- **质量门禁** — `mypy` 严格类型检查、`ruff` 代码规范、`pytest` 覆盖率不低于 80%

## 安装

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -e ".[dev]"
```

可选 OCC 内核：

```bash
pip install -e ".[occ]"
```

## CLI 用法

```bash
cad-cli --version
cad-cli file new design.json --unit mm
cad-cli draw line 0,0 100,0
cad-cli draw circle 50,50 --radius 25
cad-cli draw box 0,0,0 --dimensions 100,50,30
cad-cli edit move line_1 --dx 50
cad-cli view zoom --extents
cad-cli measure distance 0,0 100,100
```

短命令别名会被自动展开：`cad-cli l 0,0 100,0` 等价于 `cad-cli draw line 0,0 100,0`。
`cad-cli --version` 显示当前版本（例如 `cad-cli 0.2.5`）。

### 命令组

| 命令组 | 子命令 |
|--------|--------|
| `file` | new、open、save、close、list、info、export、import |
| `draw` | line、circle、arc、rectangle、polygon、polyline、box、cylinder、sphere |
| `edit` | move、copy、rotate、scale、erase、list、undo、redo |
| `view` | zoom、pan、list |
| `measure` | distance、area、list |
| `layer` | create、list、set、on、off、delete |
| `batch` | schedule、run-script、list、status、cancel、templates、logs |

## MCP Server

启动服务器，然后将任意 MCP 客户端连接到它。

### stdio（本地智能体）

```bash
python -m cad_mcp_server --transport stdio
```

### Streamable HTTP

```bash
python -m cad_mcp_server --transport http --host 127.0.0.1 --port 8081
```

服务器在 `http://127.0.0.1:8081/mcp` 提供 MCP 服务。

### 工具列表（共 47 个）

| 分组 | 工具 |
|------|------|
| 文件 | `cad_file_create`、`cad_file_open`、`cad_file_save`、`cad_file_close`、`cad_file_list` |
| 对象 | `cad_object_create`、`cad_object_read`、`cad_object_update`、`cad_object_delete`、`cad_object_list` |
| 图层 | `cad_layer_create`、`cad_layer_read`、`cad_layer_update`、`cad_layer_delete`、`cad_layer_list` |
| JSON | `cad_json_load`、`cad_json_parse`、`cad_json_validate`、`cad_json_import_geometry`、`cad_json_export_geometry`、`cad_json_import_scene`、`cad_json_export_scene`、`cad_json_save` |
| 状态 | `cad_status_check`、`cad_status_file`、`cad_status_object`、`cad_status_layer`、`cad_status_health`、`cad_logs_get`、`cad_logs_clear` |
| 校验 | `cad_validate_geometry`、`cad_validate_interference`、`cad_validate_topology`、`cad_metrics_get` |
| 渲染 | `cad_render_view` |
| 版本 | `cad_version_save`、`cad_version_list`、`cad_version_diff`、`cad_version_restore` |
| 自然语言 | `cad_nlp_command` |
| 批处理 | `cad_batch_execute`、`cad_batch_schedule`、`cad_batch_status`、`cad_batch_cancel`、`cad_batch_list`、`cad_batch_templates`、`cad_batch_run_script` |

### 校验、渲染、版本与自然语言

```text
"new file design.dwg"            -> cad_file_create  {filename: design.dwg}
"draw a line from 0,0 to 10,10"  -> cad_object_create（直线）
"render the side view"           -> cad_render_view  {view: side}
"save a version"                 -> cad_version_save
"查看状态"                        -> cad_status_health
```

版本对比使用 `deepdiff`，返回变更字段、新增/删除项与原始结果；WebGL 导出
生成 Three.js `BufferGeometry` JSON，可用 `examples/threejs_viewer.html` 预览。

### 批处理与自动化

支持标准 5 字段 Cron 表达式、依赖链与 Webhook 通知；通过沙箱脚本引擎执行
脚本，并将任务状态持久化到 SQLite：

```bash
# 一次性任务
cad-cli batch schedule commands.json --name report

# Cron 任务（每天 02:00），使用内置模板
cad-cli batch schedule commands.json --cron "0 2 * * *"

# 运行沙箱化 Python 脚本
cad-cli batch run-script script.py --type python --timeout 30

# 查看结果
cad-cli batch list
cad-cli batch status <job_id>
cad-cli batch logs --source batch --job-id <job_id>
```

脚本在隔离子进程中运行（`python -I`），带有导入白名单（`os`、`subprocess`、
`socket` 等被拦截）、运行时 `sys.modules` 防护与硬超时。

MCP 客户端配置示例（Claude Desktop `~/.config/claude/mcp.json`）：

```json
{
  "mcpServers": {
    "cad-server": {
      "command": "python",
      "args": ["-m", "cad_mcp_server", "--transport", "stdio"],
      "autoApprove": [
        "cad_object_read",
        "cad_object_list",
        "cad_status_check",
        "cad_json_load",
        "cad_json_validate",
        "cad_validate_geometry",
        "cad_metrics_get"
      ]
    }
  }
}
```

## 开发

```bash
bash scripts/setup_dev.sh   # 创建 venv + 可编辑安装 + 桩文件
bash scripts/run_tests.sh   # ruff + mypy + pytest（覆盖率门禁 >= 80%）
bash scripts/build_docs.sh
```

也可以直接运行每个门禁：

```bash
ruff check .   # 代码规范
mypy src       # 类型检查
pytest         # 测试（覆盖率门禁 >= 80%）
```

## 项目结构

```
src/cad_mcp_server/
|-- cli/            # typer CLI：命令组 + 别名展开
|-- mcp/            # MCP 服务器、传输层、安全与工具注册表
|   |-- server.py       # MCPServer 装配（47 个工具）
|   |-- transport.py    # stdio / streamable HTTP
|   |-- security.py     # 工具权限白名单
|   `-- tools/          # crud、json_ops、status、validate、batch、
|                       # render、versioning、nlp
|-- core/           # document、entity、layer、kernel、session、history、
|                   # scheduler、script_runner、batch_templates、validation、
|                   # versioning
|-- io/             # JSON / DXF / STL 导入导出
|-- schemas/        # Pydantic 几何与场景 Schema
|-- render/         # 2D / 3D PNG 渲染与 WebGL 导出
`-- utils/          # logger、config、errors、validators、units
examples/
`-- threejs_viewer.html  # 用于 WebGL 导出的浏览器查看器
tests/
|-- unit/           # CLI、core、IO、MCP 工具单元测试
`-- integration/    # MCP 端到端、批处理与 JSON 工作流测试
```

## 文档

- `AGENTS.md` — 完整开发指南与路线图
- `docs/architecture.md` — 系统架构设计
- `README.md` — 英文 README（[../README.md](../README.md)）

## 许可证

本项目采用 **Apache License 2.0**，详见 [`LICENSE`](../LICENSE)。

运行时第三方依赖全部为宽松许可（MIT / BSD / Apache-2.0 / ISC / PSF，
`certifi` 为 MPL-2.0），完整清单见
[`THIRD_PARTY_LICENSES.md`](../THIRD_PARTY_LICENSES.md)。

可选后端：`cadquery`（Apache-2.0）兼容；FreeCAD / OpenCASCADE 可选后端为
**LGPL-2.1** 且**不随包分发**，若启用需遵守 LGPL 义务（保留许可声明、
保持库可重链接）。默认的 `AnalyticKernel` 为自研实现，完全采用
Apache-2.0。
