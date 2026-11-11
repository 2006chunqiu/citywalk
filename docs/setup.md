# 建仓库与协作步骤

## 一、装工具（一次）

1. **Git**：https://git-scm.com/download/win 下载安装，一路默认。
   装完在 PowerShell 里验证：
   ```
   git --version
   ```
2. **Node.js 20 LTS**：https://nodejs.org 下载 LTS 版本，装完验证 `node -v`。
3. （可选）注册 GitHub 账号，记下用户名与邮箱。

装完在 Git 里设置身份（每台机器一次）：

```
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"
```

## 二、建空仓库（网页上，1 分钟）

1. 打开 https://github.com/new
2. Repository name 填 `citywalk`，选 **Private**
3. **不要**勾选 README、.gitignore、License（保持完全空仓库）
4. 点 Create repository

建完页面会给一段命令，复制备用。

## 三、把本地代码推上去（3 条命令）

在项目根目录（有 README.md 的那一层）执行：

```
git init
git add .
git commit -m "feat: 初始化项目骨架与接口表"
git branch -M main
git remote add origin https://github.com/你的用户名/citywalk.git
git push -u origin main
```

第一次 push 会弹窗要求登录 GitHub，按提示授权即可。

## 四、把五个组员拉进来（2 分钟）

仓库页 → **Settings** → 左侧 **Collaborators** → **Add people** → 输入组员的 GitHub 用户名 → 逐个邀请。

对方在自己邮箱里点接受，就有了推送权限。

> 提示：免费版私有仓库最多 **3 个协作者**。如果你们是 6 个人，两个选择：
> - 把仓库设为 **Public**（作品要答辩，公开一般没问题）
> - 或者用 **Gitee 私有仓库**（免费支持更多人）

## 五、每个人第一次拉代码

```
git clone https://github.com/你的用户名/citywalk.git
cd citywalk
```

## 六、日常操作（背下来就够）

```
git pull                # 开工前先拉
# ...写代码...
git add .
git commit -m "feat: 完成标签选择"
git pull                # 推之前再拉一次，避免被拒
git push
```

三个人以上同时改同一个文件会冲突，解决顺序是：

```
git pull                # 会提示冲突文件
# 打开冲突文件，把 <<<<<<< ======= >>>>>>> 之间的内容改成想要的
git add .
git commit -m "fix: 解决冲突"
git push
```

## 七、需要开分支的情况

只有「改动超过半天、且期间不想被别人的提交打断」时才开：

```
git checkout -b feat/replan
# ...写...
git push -u origin feat/replan
```

然后到 GitHub 页面点 **Compare & pull request** 合并。平时不用。

## 八、别做的事

- 不要提交 `.env`（里面是真 Key），只提交 `.env.example`
- 不要在网页上直接编辑文件后提交，容易和本地版本冲突
- 不要 `git push -f`，会覆盖别人的提交
