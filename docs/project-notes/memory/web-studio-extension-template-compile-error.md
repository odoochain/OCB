---
name: web-studio-extension-template-compile-error
description: "Fix for Odoo \"Missing (extension) parent templates web_studio.*\" style compilation failure"
metadata: 
  node_type: memory
  type: project
  originSessionId: d034b2c0-9fe2-4cef-9f4a-b3b625a535d3
---

baraka 库出现「样式编译失败 / Missing (extension) parent templates: web_studio.ViewEditor.InteractiveEditorProperties.Field」时：

根因不是数据库残留，而是某个**已安装**模块的 manifest 用贪婪 glob（`static/src/**/*.xml`）把一个 `t-inherit="web_studio.*" t-inherit-mode="extension"` 的 owl 模板扫进了**常驻** bundle `web.assets_backend`。父模板由 Enterprise 的 `web_studio` 提供（web_studio 自己也是用 `**/*.xml` glob 注册进 web.assets_backend 的）。当 `web_studio` 是 uninstalled 时父模板缺失 → backend bundle 编译失败 → 整个后端打不开。

本次肇事模块：`D:\odoochain\addons19\odoo-lawpad\lawpad_ai_pro`，文件 `static/src/field_properties_patch.xml`。它的 JS 搭档 `field_properties_patch.js` 已正确只放进 `web_studio.studio_assets_minimal`，唯独 xml 漏进了 backend。

**How to apply:** 在 manifest 的 `web.assets_backend` 里 glob 之后加 `('remove', '<module>/static/src/<patch>.xml')`，并把该 xml 放进 `web_studio.studio_assets_minimal`（和它的 js 一起）。然后 `-u <module> --stop-after-init`，再 `DELETE FROM ir_attachment WHERE name LIKE '/web/assets/%' OR name LIKE 'web.assets%'` 清旧 bundle，浏览器 Ctrl+F5。

**Why:** 这样 studio 未装时该 patch 根本不编译（不报错）；装了 studio 时随 studio bundle 正常生效，保持 studio 集成可选、不强制硬依赖 web_studio。

排查命令：`grep -rn "InteractiveEditorProperties" D:\odoochain\addons19` 找出所有定义/扩展该模板的模块。DB 端口是 5433，连库用 `$env:PGPASSWORD='odoo'; psql -h localhost -p 5433 -U odoo -d baraka`。
