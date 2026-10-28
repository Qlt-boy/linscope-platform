# 林鉴知微平台前端

当前前端由 FastAPI 从 frontend/ 托管，入口为 index.html，无需额外构建。

## 运行结构

- assets/js/api.js：HTTP、认证和文件下载客户端。
- assets/js/data.js：14 个页面的导航目录；业务、账号、权限均从后端读取。
- assets/js/app.js：路由、页面渲染、共享组件及交互。
- assets/css/tokens.css：主题变量。
- assets/css/app.css：原有组件与大屏样式。
- assets/css/workspace.css：当前工作台、响应式布局、健康页工具栏及凭据输入样式。

## 页面与关联

总览、待采集、台账、交换机/服务器/安全设备健康、告警、报告、备份、远程控制台、用户、设置、全局检索、大屏。
健康页在 URL 中保存设备和标签；同一设备的台账、告警、报告、日志通过关联菜单跳转。
采集成功进入台账，失败留在待采集区；四字段模板为序列号、设备角色、IP地址、设备地点。

## 维护约定

修改运行界面只编辑 frontend/assets 下的源码，不要编辑项目根目录中遗留的同名参考文件。
新版资源需要同步更新 index.html 的 app-build 与资源版本，再按 Docker Compose 方式发布。
空数据与读取错误必须区分；异步保存仅在成功后关闭弹窗；API 输入验证放在后端共享模块。

后端回归测试：在容器中执行 python backend/tools/test_project_regressions.py。脚本使用临时独立数据库，不连接设备。
