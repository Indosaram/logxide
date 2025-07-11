//! Pure Rust concurrency tests without PyO3

#[cfg(test)]
mod concurrency_tests {
    use crate::core_pure::{create_log_record, LogLevel, LoggerManager};
    use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
    use std::sync::{Arc, Mutex};
    use std::thread;
    use std::time::{Duration, Instant};

    #[test]
    fn test_multi_threaded_logger_creation() {
        let counter = Arc::new(AtomicU32::new(0));
        let manager = Arc::new(LoggerManager::new());
        let mut handles = Vec::new();

        // Spawn multiple threads creating loggers
        for i in 0..10 {
            let counter_clone = counter.clone();
            let manager_clone = manager.clone();
            let handle = thread::spawn(move || {
                let logger_name = format!("thread_test_{}", i);
                let logger = manager_clone.get_logger(&logger_name);

                // Verify logger properties
                assert_eq!(logger.lock().unwrap().name, logger_name);

                counter_clone.fetch_add(1, Ordering::SeqCst);
            });
            handles.push(handle);
        }

        // Wait for all threads to complete
        for handle in handles {
            handle.join().unwrap();
        }

        // Verify all threads completed
        assert_eq!(counter.load(Ordering::SeqCst), 10);
    }

    #[test]
    fn test_concurrent_logger_hierarchy() {
        let counter = Arc::new(AtomicU32::new(0));
        let manager = Arc::new(LoggerManager::new());
        let mut handles = Vec::new();

        // Spawn threads creating hierarchical loggers
        for i in 0..5 {
            let counter_clone = counter.clone();
            let manager_clone = manager.clone();
            let handle = thread::spawn(move || {
                let _parent = manager_clone.get_logger("concurrent_app");
                let child = manager_clone.get_logger(&format!("concurrent_app.module_{}", i));
                let grandchild =
                    manager_clone.get_logger(&format!("concurrent_app.module_{}.component", i));

                // Verify hierarchy
                assert!(child.lock().unwrap().parent.is_some());
                assert!(grandchild.lock().unwrap().parent.is_some());

                counter_clone.fetch_add(1, Ordering::SeqCst);
            });
            handles.push(handle);
        }

        for handle in handles {
            handle.join().unwrap();
        }

        assert_eq!(counter.load(Ordering::SeqCst), 5);
    }

    #[test]
    fn test_concurrent_log_record_creation() {
        let message_count = Arc::new(AtomicU32::new(0));
        let mut handles = Vec::new();

        // Spawn multiple threads creating log records
        for thread_id in 0..8 {
            let count_clone = message_count.clone();
            let handle = thread::spawn(move || {
                // Create multiple records from this thread
                for msg_id in 0..50 {
                    let record = create_log_record(
                        format!("concurrent_log_{}", thread_id),
                        LogLevel::Info,
                        format!("Thread {} message {}", thread_id, msg_id),
                    );

                    // Verify record properties
                    assert_eq!(record.name, format!("concurrent_log_{}", thread_id));
                    assert_eq!(record.levelno, LogLevel::Info as i32);
                    count_clone.fetch_add(1, Ordering::SeqCst);
                }
            });
            handles.push(handle);
        }

        for handle in handles {
            handle.join().unwrap();
        }

        // Should have created all records
        let total_created = message_count.load(Ordering::SeqCst);
        assert_eq!(total_created, 400); // 8 threads * 50 messages each
    }

    #[test]
    fn test_logger_level_thread_safety() {
        let manager = LoggerManager::new();
        let logger = manager.get_logger("thread_safe_level_test");
        let barrier = Arc::new(std::sync::Barrier::new(4));
        let mut handles = Vec::new();

        // Spawn threads that concurrently modify logger level
        for level_val in [
            LogLevel::Debug,
            LogLevel::Info,
            LogLevel::Warning,
            LogLevel::Error,
        ] {
            let logger_clone = logger.clone();
            let barrier_clone = barrier.clone();

            let handle = thread::spawn(move || {
                // Wait for all threads to be ready
                barrier_clone.wait();

                // Concurrently set level
                logger_clone.lock().unwrap().set_level(level_val);

                // Read back the level (should not panic)
                let current_level = logger_clone.lock().unwrap().get_effective_level();

                // Should be one of the valid levels
                assert!(matches!(
                    current_level,
                    LogLevel::Debug | LogLevel::Info | LogLevel::Warning | LogLevel::Error
                ));
            });
            handles.push(handle);
        }

        for handle in handles {
            handle.join().unwrap();
        }
    }

    #[test]
    fn test_high_volume_concurrent_logger_creation() {
        let start_time = Instant::now();
        let success_counter = Arc::new(AtomicU32::new(0));
        let manager = Arc::new(LoggerManager::new());
        let mut handles = Vec::new();

        // Spawn many threads creating loggers rapidly
        for thread_id in 0..16 {
            let counter_clone = success_counter.clone();
            let manager_clone = manager.clone();
            let handle = thread::spawn(move || {
                // Each thread creates many loggers rapidly
                for i in 0..100 {
                    let logger_name = format!("high_volume_{}_{}", thread_id, i);
                    let logger = manager_clone.get_logger(&logger_name);

                    // Verify logger was created correctly
                    assert_eq!(logger.lock().unwrap().name, logger_name);
                    counter_clone.fetch_add(1, Ordering::SeqCst);
                }
            });
            handles.push(handle);
        }

        for handle in handles {
            handle.join().unwrap();
        }

        let elapsed = start_time.elapsed();
        let total_created = success_counter.load(Ordering::SeqCst);

        // Should handle high volume efficiently
        assert_eq!(total_created, 1600); // 16 threads * 100 loggers each
        assert!(elapsed < Duration::from_secs(5)); // Should complete quickly

        println!(
            "High volume test: {} loggers created in {:?}",
            total_created, elapsed
        );
    }

    #[test]
    fn test_logger_manager_thread_safety() {
        let barrier = Arc::new(std::sync::Barrier::new(8));
        let logger_names = Arc::new(Mutex::new(Vec::new()));
        let manager = Arc::new(LoggerManager::new());
        let mut handles = Vec::new();

        // Spawn threads that all try to get the same logger
        for _i in 0..8 {
            let barrier_clone = barrier.clone();
            let names_clone = logger_names.clone();
            let manager_clone = manager.clone();

            let handle = thread::spawn(move || {
                barrier_clone.wait(); // Synchronize start

                // All threads try to get the same logger simultaneously
                let logger = manager_clone.get_logger("shared_logger");
                let name = logger.lock().unwrap().name.clone();

                names_clone.lock().unwrap().push(name);

                // Also test root logger
                let root = manager_clone.get_root_logger();
                assert_eq!(root.lock().unwrap().name, "root");
            });
            handles.push(handle);
        }

        for handle in handles {
            handle.join().unwrap();
        }

        // All threads should have gotten loggers with the correct name
        let names = logger_names.lock().unwrap();
        assert_eq!(names.len(), 8);
        for name in names.iter() {
            assert_eq!(name, "shared_logger");
        }
    }

    #[test]
    fn test_stress_test_mixed_operations() {
        let operations_completed = Arc::new(AtomicU32::new(0));
        let should_stop = Arc::new(AtomicBool::new(false));
        let manager = Arc::new(LoggerManager::new());
        let mut handles = Vec::new();

        // Logger creation workers
        for i in 0..3 {
            let counter = operations_completed.clone();
            let stop_flag = should_stop.clone();
            let manager_clone = manager.clone();
            let handle = thread::spawn(move || {
                let mut op_count = 0;
                while !stop_flag.load(Ordering::Relaxed) && op_count < 100 {
                    let logger =
                        manager_clone.get_logger(&format!("stress_logger_{}_{}", i, op_count));
                    logger.lock().unwrap().set_level(LogLevel::Info);
                    op_count += 1;
                    counter.fetch_add(1, Ordering::SeqCst);
                }
            });
            handles.push(handle);
        }

        // Record creation workers
        for i in 0..3 {
            let counter = operations_completed.clone();
            let stop_flag = should_stop.clone();
            let handle = thread::spawn(move || {
                let mut op_count = 0;
                while !stop_flag.load(Ordering::Relaxed) && op_count < 100 {
                    let record = create_log_record(
                        format!("stress_msg_{}", i),
                        LogLevel::Error,
                        format!("Stress message {} from worker {}", op_count, i),
                    );
                    // Verify record creation
                    assert_eq!(record.levelno, LogLevel::Error as i32);
                    op_count += 1;
                    counter.fetch_add(1, Ordering::SeqCst);
                }
            });
            handles.push(handle);
        }

        // Level modification workers
        for i in 0..2 {
            let counter = operations_completed.clone();
            let stop_flag = should_stop.clone();
            let manager_clone = manager.clone();
            let handle = thread::spawn(move || {
                let mut op_count = 0;
                while !stop_flag.load(Ordering::Relaxed) && op_count < 50 {
                    let logger =
                        manager_clone.get_logger(&format!("stress_level_{}_{}", i, op_count));
                    logger.lock().unwrap().set_level(LogLevel::Info);
                    op_count += 1;
                    counter.fetch_add(1, Ordering::SeqCst);
                }
            });
            handles.push(handle);
        }

        // Let the stress test run for a bit
        thread::sleep(Duration::from_millis(100));
        should_stop.store(true, Ordering::Relaxed);

        // Wait for all workers to complete
        for handle in handles {
            handle.join().unwrap();
        }

        let total_ops = operations_completed.load(Ordering::SeqCst);
        println!("Stress test completed {} operations", total_ops);

        // Should have completed significant work without panicking
        assert!(total_ops > 100);
    }
}
