# MCP反馈收集器超时时间配置参考

## 常用超时时间设置

| 时长 | 秒数 | 配置值 |
|------|------|--------|
| 5分钟 | 300 | `"MCP_DIALOG_TIMEOUT": "300"` |
| 10分钟 | 600 | `"MCP_DIALOG_TIMEOUT": "600"` |
| 15分钟 | 900 | `"MCP_DIALOG_TIMEOUT": "900"` |
| 20分钟 | 1200 | `"MCP_DIALOG_TIMEOUT": "1200"` |
| 30分钟 | 1800 | `"MCP_DIALOG_TIMEOUT": "1800"` |
| 45分钟 | 2700 | `"MCP_DIALOG_TIMEOUT": "2700"` |
| 1小时 | 3600 | `"MCP_DIALOG_TIMEOUT": "3600"` |
| 2小时 | 7200 | `"MCP_DIALOG_TIMEOUT": "7200"` |
| 4小时 | 14400 | `"MCP_DIALOG_TIMEOUT": "14400"` |
| 8小时 | 28800 | `"MCP_DIALOG_TIMEOUT": "28800"` |
| 12小时 | 43200 | `"MCP_DIALOG_TIMEOUT": "43200"` |
| 24小时 | 86400 | `"MCP_DIALOG_TIMEOUT": "86400"` |

## 配置示例

### 30分钟超时配置
```json
{
  "mcpServers": {
    "mcp-feedback-collector": {
      "command": "uv",
      "args": [
        "--directory",
        "C:/code/mcp/mcp-feedback-collector",
        "run",
        "src/mcp_feedback_collector/server.py"
      ],
      "env": {
        "PYTHONIOENCODING": "utf-8",
        "MCP_DIALOG_TIMEOUT": "1800"
      }
    }
  }
}
```

### 1小时超时配置
```json
{
  "mcpServers": {
    "mcp-feedback-collector": {
      "command": "uv",
      "args": [
        "--directory",
        "C:/code/mcp/mcp-feedback-collector",
        "run",
        "src/mcp_feedback_collector/server.py"
      ],
      "env": {
        "PYTHONIOENCODING": "utf-8",
        "MCP_DIALOG_TIMEOUT": "3600"
      }
    }
  }
}
```

## 注意事项

1. **最大限制**：系统最大支持24小时（86400秒）的超时时间
2. **重启生效**：修改配置后需要重启Cursor或重新加载MCP服务器才能生效
3. **调试信息**：启动时会在控制台显示实际读取的超时时间
4. **建议设置**：
   - 日常使用：10-20分钟（600-1200秒）
   - 长时间讨论：30-60分钟（1800-3600秒）
   - 特殊场景：2-4小时（7200-14400秒）

## 验证配置

重启MCP服务器后，查看控制台输出，应该会看到类似信息：
```
MCP反馈收集器超时时间设置为: 1800秒 (30分钟)
```