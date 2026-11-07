FROM python:3.12-slim
WORKDIR /app
COPY server.py index.html ./
ENV DB_PATH=/data/split.db PORT=8765
RUN mkdir /data && chown 1000:1000 /data
VOLUME /data
EXPOSE 8765
USER 1000:1000
CMD ["python", "-u", "server.py"]
