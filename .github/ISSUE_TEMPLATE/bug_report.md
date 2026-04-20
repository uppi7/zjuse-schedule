---
name: Bug Report
about: 报告一个接口行为异常或功能错误
title: "fix: "
labels: ["bug", "ready"]
assignees: ""
---

## 问题描述

<!-- 一句话说明出了什么问题 -->

## 复现步骤

<!-- 粘贴能复现问题的 curl 命令或操作步骤 -->

```bash
curl -X POST http://localhost:8002/api/v1/... \
  -H "X-User-Id: xxx" \
  -H "X-User-Role: ADMIN" \
  -d '{}'
```

## 期望结果

<!-- 应该返回什么 -->

## 实际结果

<!-- 实际返回了什么，粘贴响应体或错误信息 -->

```json

```

## 相关日志

<!-- docker compose logs schedule-api 的相关输出 -->

```
（粘贴日志）
```

## 环境信息

- 分支：
- 最近一次 commit：`git log --oneline -1`
