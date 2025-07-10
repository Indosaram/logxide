#!/usr/bin/env python3

import threading
import time

from logxide import logging


def demo_thread_vs_logger():
    """스레드 이름과 로거 이름의 차이점을 보여주는 데모"""

    print("=== Thread Name vs Logger Name 차이점 ===\n")

    # 포맷: 스레드 이름과 로거 이름을 모두 보여줌
    logging.basicConfig(
        format="🧵 Thread: %(threadName)-15s | 📝 Logger: %(name)-20s | %(levelname)-8s | %(message)s"
    )

    print("1. 메인 스레드에서 다양한 로거 사용:")

    # 메인 스레드 이름 설정
    logging.set_thread_name("MainThread")

    # 메인 스레드에서 여러 로거 사용
    db_logger = logging.getLogger("database.mysql")
    db_logger.setLevel(logging.INFO)
    db_logger.info("Database connection established")

    api_logger = logging.getLogger("api.users")
    api_logger.setLevel(logging.INFO)
    api_logger.info("User API endpoint called")

    cache_logger = logging.getLogger("cache.redis")
    cache_logger.setLevel(logging.INFO)
    cache_logger.warning("Cache hit ratio low")

    logging.flush()
    print()

    def worker_function(worker_id, task_type):
        """워커 스레드 함수"""
        # 스레드 이름을 Rust에 등록
        thread_name = f"{task_type.title()}Worker-{worker_id}"
        logging.set_thread_name(thread_name)

        # 각 워커는 다른 로거를 사용
        if task_type == "process":
            logger = logging.getLogger(f"worker.processor.{worker_id}")
        elif task_type == "upload":
            logger = logging.getLogger(f"worker.uploader.{worker_id}")
        else:
            logger = logging.getLogger(f"worker.general.{worker_id}")

        logger.setLevel(logging.INFO)

        # 작업 시작
        logger.info(f"Starting {task_type} task")
        time.sleep(0.1)  # 작업 시뮬레이션
        logger.info(f"Completed {task_type} task")

    print("2. 여러 스레드에서 각기 다른 로거 사용:")

    # 여러 스레드 생성 - 각각 다른 로거 사용
    threads = []

    # 프로세서 워커들
    for i in range(2):
        thread = threading.Thread(
            target=worker_function,
            args=[i, "process"],
            name=f"ProcessWorker-{i}",  # Python 스레드 이름 설정 (참고용)
        )
        threads.append(thread)

    # 업로더 워커들
    for i in range(2):
        thread = threading.Thread(
            target=worker_function,
            args=[i, "upload"],
            name=f"UploadWorker-{i}",  # Python 스레드 이름 설정 (참고용)
        )
        threads.append(thread)

    # 모든 스레드 시작
    for thread in threads:
        thread.start()

    # 모든 스레드 완료 대기
    for thread in threads:
        thread.join()

    logging.flush()
    print()

    print("📋 요약:")
    print("• threadName: 현재 코드가 실행되는 스레드의 이름")
    print("• name: 로그 메시지를 생성한 로거의 이름")
    print("• 하나의 스레드에서 여러 로거를 사용할 수 있음")
    print("• 하나의 로거가 여러 스레드에서 사용될 수 있음")


if __name__ == "__main__":
    demo_thread_vs_logger()
