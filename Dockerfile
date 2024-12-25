# 使用官方的 Python 镜像作为基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /src

#
COPY requirements.txt /src/requirements.txt

# 复制本地的 .whl 文件到容器
COPY libs/ /src/libs/

# 使用 --find-links 指定本地路径进行离线安装
RUN pip install --no-index --find-links=/libs -r /src/requirements.txt -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
https://mirrors.aliyun.com/pypi/simple/
# 删除 .whl 文件（可选）
RUN rm -rf /src/libs

# 设置容器启动命令（如果需要）
CMD ["python", "__main__.py"]
