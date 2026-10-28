# 林鉴知微平台 · LinScope Platform

基于 FastAPI、SQLite 和原生 JavaScript 的设备采集、资产台账与健康巡检平台。

## 功能

- SSH 只读采集，支持单台与批量设备；端口、账号及密码手动填写。
- 采集成功进入设备台账，失败设备保留在待采集区。
- 交换机、服务器、安全设备健康检查，告警、日志、配置备份及报告管理。
- 用户权限、操作审计、远程控制台、全局检索和巡检大屏。
- 设备导入模板：序列号、设备角色、IP地址、设备地点。

## Docker 部署

需要 Docker Engine 和 Docker Compose 插件。

```sh
cp .env.example .env
# 按实际环境修改 .env，设置管理员密码与访问域名/IP。
docker compose up -d --build
```

访问 `https://localhost:1314/`，首个管理员账号为 `admin`。
`NIP_ADMIN_PASSWORD` 留空时首次启动生成随机密码，保存在容器数据目录
`/app/backend/data/initial_admin_password.txt`。已有数据库中的用户密码不会被该变量覆盖。

默认生成自签名证书；正式部署应配置受信任的证书。
业务数据存放在 `linscope-platform-data` 卷，更新前需备份该卷。
本仓库不包含线上数据库、用户/设备凭据、证书私钥或设备导入数据。

## 开发与检查

后端依赖见 `backend/requirements.txt`；前端无需打包，由 FastAPI 直接托管。

```sh
python -m pip install -r backend/requirements.txt
python backend/run.py
python backend/tools/test_project_regressions.py
```

`backend/tools/fake_*` 为本地模拟设备工具；示例账号仅供隔离测试环境使用。
`NIP_TEST_LAB_ENABLED` 默认关闭，不应在面向公网的生产环境启用测试模拟器。
凭据使用本地加密密钥保存，备份与恢复时需同时保管数据卷中的密钥。

## 目录

- `backend/app/`：API、权限、SQLite 存储、采集及报告逻辑。
- `backend/tools/`：测试工具和模拟设备；种子脚本可能重置测试数据，执行前请阅读源码。
- `frontend/`：界面源码、主题样式、静态资源与第三方终端组件。
- `Dockerfile`、`docker-compose.yml`：容器部署配置。

## 发布与许可证状态

初始代码来自已部署的 `20261024-status10` 版本，移除了环境专属配置与运行数据。
仓库当前公开展示，尚未选择项目许可证；公开访问不代表授予使用、修改或再分发许可。
第三方组件及素材的权利仍归其各自权利人，发布衍生版本前需核对相关许可。
