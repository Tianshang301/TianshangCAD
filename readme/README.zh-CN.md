# TianshangCAD（cad-mcp-server）

一个现代化的 **CAD CLI + MCP Server** 系统。二维/三维绘图、编辑、测量、
校验以及 JSON 驱动的工作流，既可通过命令行使用，也可以作为标准化工具被任何
MCP 客户端（AI 智能体）直接调用。

> **当前状态**：Phase 1（CLI + IO）与 Phase 2（MCP Server）已完成。
> 241 个测试通过，覆盖率 82%+，`ruff` 与 `mypy` 全部通过。

**English**: [README.md](../README.md)

## 功能特性

- **CAD CLI** — `file`、`draw`、`edit`、`view`、`measure`、`layer` 等命令组，
  支持短命令别名（`l` = `draw line`、`c` = `draw circle` ……）
- **MCP Server** — 39 个 JSON-RPC 工具，支持 stdio 与 streamable HTTP 两种
  传输方式，可供 Claude、Cursor 等 MCP 客户端调用
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
cad-cli file new design.json --unit mm
cad-cli draw line 0,0 100,0
cad-cli draw circle 50,50 --radius 25
cad-cli draw box 0,0,0 --dimensions 100,50,30
cad-cli edit move line_1 --dx 50
cad-cli view zoom --extents
cad-cli measure distance 0,0 100,100
```

短命令别名会被自动展开：`cad-cli l 0,0 100,0` 等价于 `cad-cli draw line 0,0 100,0`。

### 命令组

| 命令组 | 子命令 |
|--------|--------|
| `file` | new、open、save、close、list、info、export、import |
| `draw` | line、circle、arc、rectangle、polygon、polyline、box、cylinder、sphere |
| `edit` | move、copy、rotate、scale、erase、list、undo、redo |
| `view` | zoom、pan、list |
| `measure` | distance、area、list |
| `layer` | create、list、set、on、off、delete |

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

### 工具列表（共 39 个）

| 分组 | 工具 |
|------|------|
| 文件 | `cad_file_create`、`cad_file_open`、`cad_file_save`、`cad_file_close`、`cad_file_list` |
| 对象 | `cad_object_create`、`cad_object_read`、`cad_object_update`、`cad_object_delete`、`cad_object_list` |
| 图层 | `cad_layer_create`、`cad_layer_read`、`cad_layer_update`、`cad_layer_delete`、`cad_layer_list` |
| JSON | `cad_json_load`、`cad_json_parse`、`cad_json_validate`、`cad_json_import_geometry`、`cad_json_export_geometry`、`cad_json_import_scene`、`cad_json_export_scene`、`cad_json_save` |
| 状态 | `cad_status_check`、`cad_status_file`、`cad_status_object`、`cad_status_layer`、`cad_status_health`、`cad_logs_get`、`cad_logs_clear` |
| 校验 | `cad_validate_geometry`、`cad_validate_interference`、`cad_validate_topology`、`cad_metrics_get` |
| 批处理 | `cad_batch_execute`、`cad_batch_schedule`、`cad_batch_status`、`cad_batch_cancel`、`cad_batch_list` |

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
|   |-- server.py       # MCPServer 装配（39 个工具）
|   |-- transport.py    # stdio / streamable HTTP
|   |-- security.py     # 工具权限白名单
|   `-- tools/          # crud、json_ops、status、validate、batch
|-- core/           # document、entity、layer、kernel、session、history
|-- io/             # JSON / DXF / STL 导入导出
|-- schemas/        # Pydantic 几何与场景 Schema
|-- render/         # 2D/3D 渲染（预留）
`-- utils/          # logger、config、errors、validators、units
tests/
|-- unit/           # CLI、core、IO、MCP 工具单元测试
`-- integration/    # MCP 端到端、批处理与 JSON 工作流测试
```

## 文档

- `AGENTS.md` — 完整开发指南与路线图
- `docs/architecture.md` — 系统架构设计
- `README.md` — 英文 README（[../README.md](../README.md)）
