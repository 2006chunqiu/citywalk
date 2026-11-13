@echo off
cd /d %~dp0
if not exist .venv\Scripts\python.exe (
    echo 首次运行：正在创建虚拟环境并安装依赖（约1-2分钟）...
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)
echo 后端启动中，保持本窗口开启，勿关闭。
echo 浏览器打开: http://127.0.0.1:8000/docs
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
