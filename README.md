# myownX

myownX 是一个用于课堂演示的本地 Web 社交网络平台。项目以 X 风格的信息流为参考，使用 Flask、SQLite 和 Jinja2 实现用户、动态、关系与聊天等完整的基础社交流程。

项目只面向本地运行：不依赖云端存储、第三方登录、WebSocket 或外部推荐服务。

## 功能概览

- 用户注册、登录与 POST 退出登录；注册需提供唯一邮箱。
- Sign In / Sign Up 使用与回复编辑器一致的独立悬浮模态框。
- 忘记密码：用户名和邮箱匹配后，可在 15 分钟内重新设置密码；新密码需输入两次确认。
- 个人资料查看与编辑，包括昵称、简介、头像和背景图。
- 文字动态、单图或最多四张图片动态；图片保存在本地 `static/uploads/`。
- 首页和登录后信息流：每页加载 30 条动态，Load more posts 会异步追加下一页，不刷新页面。
- 关注、取消关注、点赞、取消点赞、回复、转发和删除自己的动态；这些操作会局部更新页面。
- 动态详情页与多层回复线程，支持祖先链、继续展开和互动。
- 通知列表与未读数；私信通知与普通通知分开处理。
- 一对一私信、群聊、会话搜索与消息未读状态。
- Discover 推荐用户、热门动态，以及公开用户和动态搜索。
- 私密账号与私信权限设置。
- PC 三栏布局与移动端适配。

## 技术栈

- Python 3
- Flask 3
- Flask-SQLAlchemy
- Flask-Login
- SQLite
- Jinja2、HTML、CSS、JavaScript、Bootstrap 5

## 快速开始

### 1. 创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

如果本机虚拟环境使用的是项目中的 `bin` 目录，可以直接使用其中的 Python：

```powershell
.\.venv\bin\python.exe -m pip install -r requirements.txt
```

### 2. 创建演示数据

首次创建数据：

```powershell
.\.venv\bin\python.exe seed_data.py
```

重建干净的课堂演示数据：

```powershell
.\.venv\bin\python.exe seed_data.py --reset
```

`--reset` 会清空 `instance/myownx.db` 中的现有数据，再生成完整演示数据。

### 3. 启动应用

```powershell
.\.venv\bin\python.exe app.py
```

打开 [http://127.0.0.1:5000](http://127.0.0.1:5000)。健康检查地址为 [http://127.0.0.1:5000/health](http://127.0.0.1:5000/health)。

## 演示账号

种子数据会创建固定测试账号 `test1` 至 `test10`：

| 项目 | 值 |
| --- | --- |
| 用户名 | `test1` … `test10` |
| 显示名 | 与用户名相同 |
| 邮箱 | `test1@example.test` … `test10@example.test` |
| 密码 | `123456` |

此外还会生成 110 个 `community001` 至 `community110` 社区账号，以及本地 SVG 头像、Banner 和部分动态图片。

## 常用页面

| 页面 | 地址 | 说明 |
| --- | --- | --- |
| 首页 | `/` | 公开信息流与无刷新加载更多 |
| 信息流 | `/feed` | 登录后信息流与发布动态 |
| 发现 | `/discover` | 推荐用户与热门动态 |
| 搜索 | `/search?q=keyword` | 搜索可见用户和独立动态 |
| 通知 | `/notifications` | 普通通知列表与已读处理 |
| 私信 | `/messages` | 一对一会话、群聊与会话搜索 |
| 个人资料 | `/profile` | 当前用户资料、动态、回复与点赞 |
| 设置 | `/settings` | 私密账号与私信权限 |

所有路由、表单字段、模板变量和异步交互约定请阅读 [docs/CONTRACT.md](docs/CONTRACT.md)。已完成任务记录见 [docs/TASK_BOARD.md](docs/TASK_BOARD.md)。

## 自动化测试

```powershell
.\.venv\bin\python.exe -m unittest -v test_app.py
```

测试使用临时 SQLite 数据库，不会修改本地演示库。当前测试覆盖注册、登录、密码重置、动态、图片、关注、互动、通知、私信、群聊、搜索、隐私设置、资料关系、种子数据和信息流分页。

## 项目结构

```text
myownX/
├── app.py              # Flask 路由、业务逻辑与 SQLite 迁移
├── models.py           # SQLAlchemy 数据模型
├── config.py           # 本地 SQLite 配置
├── seed_data.py        # 大规模演示数据与本地 SVG 资源生成
├── test_app.py         # 自动化回归测试
├── templates/          # Jinja2 页面与组件模板
├── static/             # CSS、JavaScript、默认资源与本地上传文件
├── instance/           # 本地 SQLite 数据库
└── docs/               # 契约、任务记录和需求文档
```

## 开发约定

- 后端与前端契约以 [docs/CONTRACT.md](docs/CONTRACT.md) 为准。
- 每次只处理一个任务，修改后运行测试。
- 对模板、路由和表单字段的改动应同步更新契约文档。
