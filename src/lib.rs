#![allow(non_snake_case)]

use pyo3::prelude::*;

mod config;
pub mod core;
mod fast_logger;
mod filter;
pub mod formatter;
mod globals;
pub mod handler;
mod py_handlers;
mod py_logger;
mod string_cache;

pub use core::{create_log_record_with_extra, LogLevel, LogRecord};
pub use globals::{HANDLERS, THREAD_NAME};
pub use py_handlers::{
    PyBufferedHTTPHandler, PyFileHandler, PyRotatingFileHandler, PyStreamHandler,
};
pub use py_logger::PyLogger;

#[pymodule]
fn logxide(_py: Python, m: &Bound<'_, pyo3::types::PyModule>) -> PyResult<()> {
    let logging_module = PyModule::new(m.py(), "logging")?;
    logging_module.add_class::<PyLogger>()?;
    logging_module.add_class::<LogRecord>()?;
    logging_module.add_class::<PyFileHandler>()?;
    logging_module.add_class::<PyStreamHandler>()?;
    logging_module.add_class::<PyRotatingFileHandler>()?;
    logging_module.add_class::<PyBufferedHTTPHandler>()?;
    logging_module.add_function(wrap_pyfunction!(globals::get_logger, &logging_module)?)?;
    logging_module.add_function(wrap_pyfunction!(globals::basicConfig, &logging_module)?)?;
    logging_module.add_function(wrap_pyfunction!(globals::flush, &logging_module)?)?;
    logging_module.add_function(wrap_pyfunction!(globals::set_thread_name, &logging_module)?)?;
    logging_module.add_function(wrap_pyfunction!(
        globals::register_http_handler,
        &logging_module
    )?)?;
    logging_module.add_function(wrap_pyfunction!(globals::clear_handlers, &logging_module)?)?;
    logging_module.add_function(wrap_pyfunction!(
        globals::register_file_handler,
        &logging_module
    )?)?;
    logging_module.add_function(wrap_pyfunction!(
        globals::register_rotating_file_handler,
        &logging_module
    )?)?;
    m.add_submodule(&logging_module)?;

    m.add_class::<PyLogger>()?;
    m.add_class::<LogRecord>()?;
    m.add_class::<PyFileHandler>()?;
    m.add_class::<PyStreamHandler>()?;
    m.add_class::<PyRotatingFileHandler>()?;
    m.add_class::<PyBufferedHTTPHandler>()?;
    m.add_function(wrap_pyfunction!(globals::get_logger, m)?)?;
    m.add_function(wrap_pyfunction!(globals::basicConfig, m)?)?;
    m.add_function(wrap_pyfunction!(globals::flush, m)?)?;
    m.add_function(wrap_pyfunction!(globals::set_thread_name, m)?)?;
    m.add_function(wrap_pyfunction!(globals::register_http_handler, m)?)?;
    m.add_function(wrap_pyfunction!(globals::clear_handlers, m)?)?;
    m.add_function(wrap_pyfunction!(globals::register_file_handler, m)?)?;
    m.add_function(wrap_pyfunction!(
        globals::register_rotating_file_handler,
        m
    )?)?;
    Ok(())
}
