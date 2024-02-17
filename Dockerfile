# 使用一个基础的 Python 镜像作为基础
FROM python:3.10-slim-buster

# 设置工作目录
WORKDIR /app

# 将应用程序的依赖项安装到容器中
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 将应用程序代码复制到容器中
COPY . .

# 暴露应用程序运行的端口
EXPOSE 5000

# 设置环境变量
ENV FLASK_APP=app.py

# 运行应用程序
CMD ["flask", "run", "--host=0.0.0.0"]
