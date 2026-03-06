//! PyLogger - Python-exposed logger implementation

#![allow(non_snake_case)]

use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict, PyList, PyTuple};
use pyo3::IntoPyObjectExt;
use serde_json::Value;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use crate::core::{create_log_record_with_extra, LogLevel, LogRecord, Logger};
use crate::fast_logger::FastLogger;
use crate::globals::{add_handler_to_registry, HANDLERS};
use crate::handler::Handler;

/// Check and resolve a log level from either an integer or a string name.
/// Handles: int passthrough, string lookup (CRITICAL/FATAL/ERROR/WARN/WARNING/INFO/DEBUG/NOTSET).
/// Raises TypeError for unsupported types, ValueError for unknown level names.
pub fn check_level(py: Python, level: &Bound<PyAny>) -> PyResult<u32> {
    // Try int first
    if let Ok(i) = level.extract::<u32>() {
        return Ok(i);
    }
    // Try i64 for negative or large values, then cast
    if let Ok(i) = level.extract::<i64>() {
        return Ok(i as u32);
    }
    // Try string
    if let Ok(s) = level.extract::<String>() {
        let upper = s.to_uppercase();
        return match upper.as_str() {
            "CRITICAL" | "FATAL" => Ok(50),
            "ERROR" => Ok(40),
            "WARN" | "WARNING" => Ok(30),
            "INFO" => Ok(20),
            "DEBUG" => Ok(10),
            "NOTSET" => Ok(0),
            _ => {
                // Try Python-side _nameToLevel lookup for custom levels
                let compat = py.import("logxide.compat_functions")?;
                let name_to_level = compat.getattr("_nameToLevel")?;
                match name_to_level.call_method1("get", (upper.as_str(),)) {
                    Ok(val) if !val.is_none() => val.extract::<u32>(),
                    _ => Err(pyo3::exceptions::PyValueError::new_err(
                        format!("Unknown level: '{}'", s),
                    )),
                }
            }
        };
    }
    Err(pyo3::exceptions::PyTypeError::new_err(
        format!("Level not an integer or a valid string: {}", level.repr()?.to_string()),
    ))
}
pub fn py_to_json_value(obj: &Bound<PyAny>) -> Value {
    if obj.is_none() {
        Value::Null
    } else if let Ok(b) = obj.extract::<bool>() {
        Value::Bool(b)
    } else if let Ok(i) = obj.extract::<i64>() {
        Value::Number(i.into())
    } else if let Ok(f) = obj.extract::<f64>() {
        serde_json::Number::from_f64(f)
            .map(Value::Number)
            .unwrap_or(Value::Null)
    } else if let Ok(s) = obj.extract::<String>() {
        Value::String(s)
    } else if let Ok(list) = obj.cast::<PyList>() {
        let arr: Vec<Value> = list.iter().map(|item| py_to_json_value(&item)).collect();
        Value::Array(arr)
    } else if let Ok(tuple) = obj.cast::<PyTuple>() {
        let arr: Vec<Value> = tuple.iter().map(|item| py_to_json_value(&item)).collect();
        Value::Array(arr)
    } else if let Ok(dict) = obj.cast::<PyDict>() {
        let mut map = serde_json::Map::new();
        for (k, v) in dict.iter() {
            if let Ok(key) = k.str() {
                map.insert(key.to_string(), py_to_json_value(&v));
            }
        }
        Value::Object(map)
    } else if let Ok(s) = obj.str() {
        Value::String(s.to_string())
    } else {
        Value::Null
    }
}

#[pyclass(skip_from_py_object)]
pub struct PyLogger {
    pub(crate) inner: Arc<Mutex<Logger>>,
    pub(crate) fast_logger: Arc<FastLogger>,
    pub(crate) local_handlers: Arc<Mutex<Vec<Arc<dyn Handler + Send + Sync>>>>,
    pub(crate) local_python_handlers: Arc<Mutex<Vec<Py<PyAny>>>>,
    pub(crate) filters: Arc<Mutex<Vec<Py<PyAny>>>>,
    pub(crate) propagate: Arc<Mutex<bool>>,
    pub(crate) parent: Arc<Mutex<Option<Py<PyAny>>>>,
    pub(crate) manager: Arc<Mutex<Option<Py<PyAny>>>>,
}

impl PyLogger {
    pub fn new(name: &str) -> Self {
        let fast_logger = Arc::new(FastLogger::new(name));
        PyLogger {
            inner: Arc::new(Mutex::new(Logger::new(name))),
            fast_logger,
            local_handlers: Arc::new(Mutex::new(Vec::new())),
            local_python_handlers: Arc::new(Mutex::new(Vec::new())),
            filters: Arc::new(Mutex::new(Vec::new())),
            propagate: Arc::new(Mutex::new(true)),
            parent: Arc::new(Mutex::new(None)),
            manager: Arc::new(Mutex::new(None)),
        }
    }

    pub fn with_params(
        inner: Arc<Mutex<Logger>>,
        fast_logger: Arc<FastLogger>,
        manager: Option<Py<PyAny>>,
    ) -> Self {
        PyLogger {
            inner,
            fast_logger,
            local_handlers: Arc::new(Mutex::new(Vec::new())),
            local_python_handlers: Arc::new(Mutex::new(Vec::new())),
            filters: Arc::new(Mutex::new(Vec::new())),
            propagate: Arc::new(Mutex::new(true)),
            parent: Arc::new(Mutex::new(None)),
            manager: Arc::new(Mutex::new(manager)),
        }
    }
}

impl Clone for PyLogger {
    fn clone(&self) -> Self {
        PyLogger {
            inner: self.inner.clone(),
            fast_logger: self.fast_logger.clone(),
            local_handlers: self.local_handlers.clone(),
            local_python_handlers: self.local_python_handlers.clone(),
            filters: self.filters.clone(),
            propagate: self.propagate.clone(),
            parent: self.parent.clone(),
            manager: self.manager.clone(),
        }
    }
}

impl Drop for PyLogger {
    fn drop(&mut self) {}
}

impl PyLogger {
    fn extract_extra_fields(
        &self,
        kwargs: Option<&Bound<PyDict>>,
    ) -> Option<HashMap<String, Value>> {
        kwargs.and_then(|dict| {
            if let Ok(Some(extra_bound)) = dict.get_item("extra") {
                if let Ok(extra_dict) = extra_bound.cast::<PyDict>() {
                    let mut extra_map = HashMap::new();
                    for (key, value) in extra_dict.iter() {
                        if let Ok(key_str) = key.str() {
                            let json_value = py_to_json_value(&value);
                            extra_map.insert(key_str.to_string(), json_value);
                        }
                    }
                    return Some(extra_map);
                }
            }
            None
        })
    }

    /// Extract exc_info from kwargs and format it as traceback text.
    /// `default_exc_info`: if true, capture current exception when exc_info kwarg is absent.
    /// Handles: exc_info=True, exc_info=False, exc_info=(type, value, tb), exc_info=<exception>.
    fn extract_exc_info_text(
        &self,
        py: Python,
        kwargs: Option<&Bound<PyDict>>,
        default_exc_info: bool,
    ) -> Option<String> {
        let exc_info_val = kwargs.and_then(|dict| {
            dict.get_item("exc_info").ok().flatten()
        });

        match exc_info_val {
            None => {
                if !default_exc_info {
                    return None;
                }
                self.capture_current_exception(py)
            }
            Some(val) => {
                // Check if it's a tuple (type, value, tb)
                if let Ok(tuple) = val.cast::<PyTuple>() {
                    if tuple.len() == 3 {
                        let val_item = tuple.get_item(1).ok();
                        if val_item.map(|v| !v.is_none()).unwrap_or(false) {
                            return self.format_exception_tuple(py, tuple);
                        }
                    }
                    // (None, None, None) or wrong-length tuple
                    return None;
                }

                // Check if it's an exception instance
                if let Ok(base_exc) = py.import("builtins").and_then(|m| m.getattr("BaseException")) {
                    if val.is_instance(&base_exc).unwrap_or(false) {
                        return self.format_exception_instance(py, &val);
                    }
                }

                // Otherwise check truthiness (handles True, False, 0, 1, etc.)
                if val.is_truthy().unwrap_or(false) {
                    self.capture_current_exception(py)
                } else {
                    None
                }
            }
        }
    }

    /// Extract the raw exc_info Python object from kwargs for passing to Python handlers.
    /// Returns the original (type, value, tb) tuple, sys.exc_info() result, or None.
    fn extract_exc_info_raw(
        &self,
        py: Python,
        kwargs: Option<&Bound<PyDict>>,
        default_exc_info: bool,
    ) -> Option<Py<PyAny>> {
        let exc_info_val = kwargs.and_then(|dict| {
            dict.get_item("exc_info").ok().flatten()
        });

        match exc_info_val {
            None => {
                if !default_exc_info {
                    return None;
                }
                // Capture current exception as sys.exc_info() tuple
                py.import("sys")
                    .and_then(|m| m.call_method0("exc_info"))
                    .ok()
                    .and_then(|info| {
                        // Check if there's an actual exception (info[1] is not None)
                        let tuple = info.cast::<PyTuple>().ok()?;
                        let val_item = tuple.get_item(1).ok()?;
                        if val_item.is_none() { None } else { Some(info.unbind()) }
                    })
            }
            Some(val) => {
                // Already a tuple — pass through directly
                if let Ok(tuple) = val.cast::<PyTuple>() {
                    if tuple.len() == 3 {
                        let val_item = tuple.get_item(1).ok();
                        if val_item.map(|v| !v.is_none()).unwrap_or(false) {
                            return Some(val.unbind());
                        }
                    }
                    return None;
                }

                // Exception instance — build (type, value, tb) tuple
                if let Ok(base_exc) = py.import("builtins").and_then(|m| m.getattr("BaseException")) {
                    if val.is_instance(&base_exc).unwrap_or(false) {
                        let exc_type = val.get_type();
                        let tb = val.getattr("__traceback__").ok();
                        let tuple = PyTuple::new(py, &[
                            exc_type.into_any(),
                            val.clone(),
                            tb.unwrap_or_else(|| py.None().into_bound(py)),
                        ]).ok()?;
                        return Some(tuple.unbind().into());
                    }
                }

                // True → capture sys.exc_info()
                if val.is_truthy().unwrap_or(false) {
                    py.import("sys")
                        .and_then(|m| m.call_method0("exc_info"))
                        .ok()
                        .and_then(|info| {
                            let tuple = info.cast::<PyTuple>().ok()?;
                            let val_item = tuple.get_item(1).ok()?;
                            if val_item.is_none() { None } else { Some(info.unbind()) }
                        })
                } else {
                    None
                }
            }
        }
    }

    /// Capture the current active exception via traceback.format_exc().
    fn capture_current_exception(&self, py: Python) -> Option<String> {
        py.import("traceback")
            .and_then(|m| m.call_method0("format_exc"))
            .map(|s| s.to_string())
            .ok()
            .filter(|s| s != "NoneType: None\n" && !s.is_empty())
    }

    /// Format a (type, value, tb) tuple into traceback text.
    fn format_exception_tuple(&self, py: Python, tuple: &Bound<PyTuple>) -> Option<String> {
        let tb_mod = py.import("traceback").ok()?;
        let formatted = tb_mod.call_method1(
            "format_exception",
            (tuple.get_item(0).ok()?, tuple.get_item(1).ok()?, tuple.get_item(2).ok()?),
        ).ok()?;
        let empty_str = "".into_pyobject(py).ok()?;
        let joined = empty_str.call_method1("join", (&formatted,)).ok()?;
        let result = joined.to_string();
        if result.is_empty() { None } else { Some(result) }
    }

    /// Format an exception instance into traceback text.
    fn format_exception_instance(&self, py: Python, exc: &Bound<PyAny>) -> Option<String> {
        let exc_type = exc.get_type();
        let tb = exc.getattr("__traceback__").ok()?;
        let tb_mod = py.import("traceback").ok()?;
        let formatted = tb_mod.call_method1(
            "format_exception",
            (exc_type, exc, tb),
        ).ok()?;
        let empty_str = "".into_pyobject(py).ok()?;
        let joined = empty_str.call_method1("join", (&formatted,)).ok()?;
        let result = joined.to_string();
        if result.is_empty() { None } else { Some(result) }
    }

    /// Populate pathname, filename, lineno, func_name on record via Python frame introspection.
    /// Uses sys._getframe(0) from Rust — which gives the last Python frame (the caller).
    fn populate_caller_info(py: Python, record: &mut LogRecord) {
        let Ok(sys) = py.import("sys") else { return };
        // _getframe(0) from Rust returns the most recent Python frame,
        // which is the frame that called logger.debug/info/etc.
        let Ok(frame) = sys.call_method1("_getframe", (0i32,)) else { return };

        // Extract f_code.co_filename → pathname, filename
        if let Ok(code) = frame.getattr("f_code") {
            if let Ok(co_filename) = code.getattr("co_filename") {
                if let Ok(path) = co_filename.extract::<String>() {
                    // filename = basename of pathname
                    let filename = path.rsplit_once(std::path::MAIN_SEPARATOR)
                        .map(|(_, name)| name.to_string())
                        .unwrap_or_else(|| path.clone());
                    // module = filename without extension
                    let module_name = filename.rsplit_once('.')
                        .map(|(base, _)| base.to_string())
                        .unwrap_or_else(|| filename.clone());
                    record.pathname = path;
                    record.filename = filename;
                    record.module = module_name;
                }
            }
            if let Ok(co_name) = code.getattr("co_name") {
                if let Ok(func) = co_name.extract::<String>() {
                    record.func_name = func;
                }
            }
        }

        // Extract f_lineno → lineno
        if let Ok(lineno) = frame.getattr("f_lineno") {
            if let Ok(line) = lineno.extract::<u32>() {
                record.lineno = line;
            }
        }
    }
}

#[pymethods]
impl PyLogger {
    fn emit_record(&self, mut record: LogRecord, exc_info_py: Option<Py<PyAny>>) {
        // Apply Python callable filters before emission
        // Filters can modify the record (especially record.msg) and return False to suppress
        let should_emit = Python::attach(|py| {
            let filters = self.filters.lock().unwrap();
            for filter_obj in filters.iter() {
                let filter_bound = filter_obj.bind(py);
                
                // Try calling filter.filter(record) if it's a filter object
                // Or call it directly if it's a callable
                let result = if let Ok(filter_method) = filter_bound.getattr("filter") {
                    // Create a mutable Python dict to represent the record
                    let py_record = pyo3::types::PyDict::new(py);
                    let _ = py_record.set_item("name", &record.name);
                    let _ = py_record.set_item("levelno", record.levelno);
                    let _ = py_record.set_item("levelname", &record.levelname);
                    let _ = py_record.set_item("msg", &record.msg);
                    let _ = py_record.set_item("pathname", &record.pathname);
                    let _ = py_record.set_item("lineno", record.lineno);
                    let _ = py_record.set_item("func_name", &record.func_name);
                    
                    // Call filter method with reference to dict
                    let call_result = filter_method.call1((&py_record,));
                    
                    // Check if filter modified the msg (after the call)
                    if let Ok(Some(new_msg)) = py_record.get_item("msg") {
                        if let Ok(msg_str) = new_msg.extract::<String>() {
                            record.msg = msg_str;
                        }
                    }
                    
                    match call_result {
                        Ok(res) => res.is_truthy().unwrap_or(true),
                        Err(_) => true,  // On error, allow the record
                    }
                } else if filter_bound.is_callable() {
                    // Direct callable filter
                    let py_record = pyo3::types::PyDict::new(py);
                    let _ = py_record.set_item("name", &record.name);
                    let _ = py_record.set_item("levelno", record.levelno);
                    let _ = py_record.set_item("levelname", &record.levelname);
                    let _ = py_record.set_item("msg", &record.msg);
                    let _ = py_record.set_item("pathname", &record.pathname);
                    let _ = py_record.set_item("lineno", record.lineno);
                    let _ = py_record.set_item("func_name", &record.func_name);
                    
                    // Call filter with reference to dict
                    let call_result = filter_bound.call1((&py_record,));
                    
                    // Check if filter modified the msg (after the call)
                    if let Ok(Some(new_msg)) = py_record.get_item("msg") {
                        if let Ok(msg_str) = new_msg.extract::<String>() {
                            record.msg = msg_str;
                        }
                    }
                    
                    match call_result {
                        Ok(res) => res.is_truthy().unwrap_or(true),
                        Err(_) => true,
                    }
                } else {
                    true  // Not a valid filter, allow the record
                };
                
                if !result {
                    return false;  // Filter rejected the record
                }
            }
            true  // All filters passed
        });
        
        if !should_emit {
            return;
        }
        
        let local_handlers = self.local_handlers.lock().unwrap();

        // 1. Handle Rust handlers
        if local_handlers.is_empty() {
            drop(local_handlers);
            let global_handlers = HANDLERS.lock().unwrap();
            for handler in global_handlers.iter() {
                let _ = futures::executor::block_on(handler.emit(&record));
            }
        } else {
            for handler in local_handlers.iter() {
                let _ = futures::executor::block_on(handler.emit(&record));
            }

            let should_propagate = *self.propagate.lock().unwrap();
            if should_propagate {
                drop(local_handlers);
                let global_handlers = HANDLERS.lock().unwrap();
                for handler in global_handlers.iter() {
                    let _ = futures::executor::block_on(handler.emit(&record));
                }
            }
        }

        // 2. Handle Python handlers (like pytest's caplog)
        Python::attach(|py| {
            let local_py = self.local_python_handlers.lock().unwrap();
            let global_py = crate::globals::PYTHON_HANDLERS_KEEP_ALIVE.lock().unwrap();

            if local_py.is_empty() && global_py.is_empty() {
                return;
            }

            // Create a proper Python LogRecord
            let py_record = match self.makeRecord(
                py,
                record.name.clone(),
                record.levelno,
                record.pathname.clone(),
                record.lineno as i32,
                record.get_message().into_py_any(py).expect("Failed to convert getMessage to PyAny").into(),
                py.None().into(),
                exc_info_py.as_ref().map(|e| e.clone_ref(py)),
            ) {
                Ok(r) => r,
                Err(_) => {
                    return;
                }
            };

            // Set exc_text on the Python LogRecord so stdlib Formatter.format() appends it
            if let Some(ref exc_text) = record.exc_text {
                let _ = py_record.bind(py).setattr("exc_text", exc_text.as_str());
            }

            // Set func_name/funcName on the Python LogRecord from Rust record's caller info
            if !record.func_name.is_empty() {
                let _ = py_record.bind(py).setattr("func_name", record.func_name.as_str());
                let _ = py_record.bind(py).setattr("funcName", record.func_name.as_str());
            }

            // Call local Python handlers
            for handler in local_py.iter() {
                let b_handler = handler.bind(py);
                let _ = b_handler.call_method1("handle", (&py_record,));
            }
            // Call global Python handlers
            for handler in global_py.iter() {
                let b_handler = handler.bind(py);
                let _ = b_handler.call_method1("handle", (&py_record,));
            }
        });
    }

    #[getter]
    fn name(&self) -> PyResult<String> {
        Ok(self.fast_logger.name.to_string())
    }

    #[getter]
    fn level(&self) -> PyResult<u32> {
        Ok(self.fast_logger.get_level() as u32)
    }

    #[getter]
    fn handlers(&self, py: Python) -> PyResult<Py<PyAny>> {
        Ok(PyList::empty(py).into())
    }

    #[setter]
    fn set_handlers(&self, _handlers: Py<PyAny>) -> PyResult<()> {
        Ok(())
    }

    #[getter]
    fn disabled(&self) -> PyResult<bool> {
        Ok(false)
    }

    #[getter]
    fn propagate(&self) -> PyResult<bool> {
        let propagate = self.propagate.lock().unwrap();
        Ok(*propagate)
    }

    #[setter]
    fn set_propagate(&self, value: bool) -> PyResult<()> {
        let mut propagate = self.propagate.lock().unwrap();
        *propagate = value;
        Ok(())
    }

    #[getter]
    fn parent(&self, py: Python) -> PyResult<Option<Py<PyAny>>> {
        let parent_lock = self.parent.lock().unwrap();
        Ok(parent_lock.as_ref().map(|p| p.clone_ref(py)))
    }

    #[setter]
    fn set_parent(&self, value: Option<Py<PyAny>>) -> PyResult<()> {
        let mut parent = self.parent.lock().unwrap();
        *parent = value;
        Ok(())
    }

    #[getter]
    fn manager(&self, py: Python) -> PyResult<Option<Py<PyAny>>> {
        let manager_lock = self.manager.lock().unwrap();
        Ok(manager_lock.as_ref().map(|m| m.clone_ref(py)))
    }

    #[setter]
    fn set_manager(&self, value: Option<Py<PyAny>>) -> PyResult<()> {
        let mut manager = self.manager.lock().unwrap();
        *manager = value;
        Ok(())
    }

    #[getter]
    fn root(&self, py: Python) -> PyResult<PyLogger> {
        crate::globals::get_logger(py, Some("root"), None)
    }

    fn filter(&self, record: Py<PyAny>) -> PyResult<bool> {
        Python::attach(|py| {
            let record_bound = record.bind(py);
            let rust_record = record_bound.extract::<LogRecord>()?;
            let inner_logger = self.inner.lock().unwrap();
            for filter in &inner_logger.filters {
                if !filter.filter(&rust_record) {
                    return Ok(false);
                }
            }
            Ok(true)
        })
    }

    fn setLevel(&mut self, py: Python, level: &Bound<PyAny>) -> PyResult<()> {
        let level_int = check_level(py, level)?;
        let level = LogLevel::from_usize(level_int as usize);
        self.fast_logger.set_level(level);
        self.inner.lock().unwrap().set_level(level);
        crate::fast_logger::propagate_all_effective_levels();
        Ok(())
    }

    fn getEffectiveLevel(&self) -> PyResult<u32> {
        Ok(self.fast_logger.get_effective_level())
    }

    fn addHandler(&self, _py: Python, handler: &Bound<PyAny>) -> PyResult<()> {
        add_handler_to_registry(
            handler,
            &self.fast_logger.name,
            &self.local_handlers,
            &self.local_python_handlers,
        )?;

        Ok(())
    }

    /// Add a filter to this logger.
    /// The filter can be:
    /// - An object with a `filter(record)` method that returns True/False
    /// - A callable that takes a record dict and returns True/False
    /// 
    /// The record dict has keys: name, levelno, levelname, msg, pathname, lineno, func_name
    /// Filters can modify record['msg'] to transform the log message.
    fn addFilter(&self, py: Python, filter_obj: Py<PyAny>) -> PyResult<()> {
        let mut filters = self.filters.lock().unwrap();
        filters.push(filter_obj.clone_ref(py));
        Ok(())
    }

    /// Remove a filter from this logger.
    fn removeFilter(&self, py: Python, filter_obj: &Bound<PyAny>) -> PyResult<()> {
        let mut filters = self.filters.lock().unwrap();
        filters.retain(|f| !f.bind(py).is(filter_obj));
        Ok(())
    }

    fn serialize_args(&self, _py: Python, args: &Bound<PyAny>) -> Option<String> {
        let args_tuple = match args.cast::<PyTuple>() {
            Ok(t) if !t.is_empty() => t,
            _ => return None,
        };
        // If args is a single dict (e.g., `log("%(key)s", {"key": "v"})`) unwrap it
        // so that `msg % args` works correctly (dict, not tuple-of-dict).
        let json_val = if args_tuple.len() == 1 {
            let first = args_tuple.get_item(0).expect("Failed to get first arg");
            if first.cast::<PyDict>().is_ok() {
                py_to_json_value(&first)
            } else {
                py_to_json_value(args_tuple.as_any())
            }
        } else {
            py_to_json_value(args_tuple.as_any())
        };
        Some(serde_json::to_string(&json_val).expect("Failed to serialize args to JSON"))
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn debug(
        &self,
        py: Python,
        msg: Py<PyAny>,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        if !self.fast_logger.is_enabled_for(LogLevel::Debug) {
            return Ok(());
        }
        let extra_fields = self.extract_extra_fields(kwargs);
        let msg_str = msg.bind(py).str()?.to_string();
        let serialized_args = self.serialize_args(py, args);
        let mut record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Debug,
            msg_str,
            extra_fields,
        );
        PyLogger::populate_caller_info(py, &mut record);
        record.args = serialized_args;
        record.exc_text = self.extract_exc_info_text(py, kwargs, false);
        let exc_info_py = self.extract_exc_info_raw(py, kwargs, false);
        self.emit_record(record, exc_info_py);
        Ok(())
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn info(
        &self,
        py: Python,
        msg: Py<PyAny>,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        if !self.fast_logger.is_enabled_for(LogLevel::Info) {
            return Ok(());
        }
        let extra_fields = self.extract_extra_fields(kwargs);
        let msg_str = msg.bind(py).str()?.to_string();
        let serialized_args = self.serialize_args(py, args);
        let mut record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Info,
            msg_str,
            extra_fields,
        );
        PyLogger::populate_caller_info(py, &mut record);
        record.args = serialized_args;
        record.exc_text = self.extract_exc_info_text(py, kwargs, false);
        let exc_info_py = self.extract_exc_info_raw(py, kwargs, false);
        self.emit_record(record, exc_info_py);
        Ok(())
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn warning(
        &self,
        py: Python,
        msg: Py<PyAny>,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        if !self.fast_logger.is_enabled_for(LogLevel::Warning) {
            return Ok(());
        }
        let extra_fields = self.extract_extra_fields(kwargs);
        let msg_str = msg.bind(py).str()?.to_string();
        let serialized_args = self.serialize_args(py, args);
        let mut record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Warning,
            msg_str,
            extra_fields,
        );
        PyLogger::populate_caller_info(py, &mut record);
        record.args = serialized_args;
        record.exc_text = self.extract_exc_info_text(py, kwargs, false);
        let exc_info_py = self.extract_exc_info_raw(py, kwargs, false);
        self.emit_record(record, exc_info_py);
        Ok(())
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn error(
        &self,
        py: Python,
        msg: Py<PyAny>,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        if !self.fast_logger.is_enabled_for(LogLevel::Error) {
            return Ok(());
        }
        let extra_fields = self.extract_extra_fields(kwargs);
        let msg_str = msg.bind(py).str()?.to_string();
        let serialized_args = self.serialize_args(py, args);
        let mut record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Error,
            msg_str,
            extra_fields,
        );
        PyLogger::populate_caller_info(py, &mut record);
        record.args = serialized_args;
        record.exc_text = self.extract_exc_info_text(py, kwargs, false);
        let exc_info_py = self.extract_exc_info_raw(py, kwargs, false);
        self.emit_record(record, exc_info_py);
        Ok(())
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn critical(
        &self,
        py: Python,
        msg: Py<PyAny>,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        if !self.fast_logger.is_enabled_for(LogLevel::Critical) {
            return Ok(());
        }
        let extra_fields = self.extract_extra_fields(kwargs);
        let msg_str = msg.bind(py).str()?.to_string();
        let serialized_args = self.serialize_args(py, args);
        let mut record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Critical,
            msg_str,
            extra_fields,
        );
        PyLogger::populate_caller_info(py, &mut record);
        record.args = serialized_args;
        record.exc_text = self.extract_exc_info_text(py, kwargs, false);
        let exc_info_py = self.extract_exc_info_raw(py, kwargs, false);
        self.emit_record(record, exc_info_py);
        Ok(())
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn exception(
        &self,
        py: Python,
        msg: Py<PyAny>,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        if !self.fast_logger.is_enabled_for(LogLevel::Error) {
            return Ok(());
        }
        let extra_fields = self.extract_extra_fields(kwargs);
        let msg_str = msg.bind(py).str()?.to_string();
        let serialized_args = self.serialize_args(py, args);
        let mut record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Error,
            msg_str,
            extra_fields,
        );
        PyLogger::populate_caller_info(py, &mut record);
        record.args = serialized_args;
        record.exc_text = self.extract_exc_info_text(py, kwargs, true);
        let exc_info_py = self.extract_exc_info_raw(py, kwargs, true);
        self.emit_record(record, exc_info_py);
        Ok(())
    }

    #[pyo3(signature = (level, msg, *args, **kwargs))]
    fn log(
        &self,
        py: Python,
        level: u32,
        msg: Py<PyAny>,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        let log_level = LogLevel::from_usize(level as usize);
        if !self.fast_logger.is_enabled_for(log_level) {
            return Ok(());
        }
        let extra_fields = self.extract_extra_fields(kwargs);
        let msg_str = msg.bind(py).str()?.to_string();
        let serialized_args = self.serialize_args(py, args);
        let mut record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            log_level,
            msg_str,
            extra_fields,
        );
        PyLogger::populate_caller_info(py, &mut record);
        record.args = serialized_args;
        record.exc_text = self.extract_exc_info_text(py, kwargs, false);
        let exc_info_py = self.extract_exc_info_raw(py, kwargs, false);
        self.emit_record(record, exc_info_py);
        Ok(())
    }

    #[pyo3(signature = (name, level, fn_, lno, msg, args, exc_info=None))]
    fn makeRecord(
        &self,
        py: Python,
        name: String,
        level: i32,
        fn_: String,
        lno: i32,
        msg: Py<PyAny>,
        args: Py<PyAny>,
        exc_info: Option<Py<PyAny>>,
    ) -> PyResult<Py<PyAny>> {
        let logging = py.import("logging")?;
        let log_record_cls = logging.getattr("LogRecord")?;

        // Standard LogRecord constructor:
        // name, level, pathname, lineno, msg, args, exc_info, func=None, sinfo=None
        let args_tuple = (
            name,
            level,
            fn_,
            lno,
            msg,
            args,
            exc_info,
            py.None(), // func
            py.None(), // sinfo
        );

        let record = log_record_cls.call1(args_tuple)?;
        Ok(record.unbind())
    }

    fn handle(&self, record: Py<PyAny>) -> PyResult<()> {
        Python::attach(|py| {
            let handlers = crate::globals::PYTHON_HANDLERS_KEEP_ALIVE.lock().unwrap();
            for handler in handlers.iter() {
                let _ = handler.call_method1(py, "handle", (record.clone_ref(py),));
            }
        });
        Ok(())
    }

    fn callHandlers(&self, record: Py<PyAny>) -> PyResult<()> {
        self.handle(record)
    }

    #[pyo3(signature = (suffix))]
    fn getChild(slf: PyRef<Self>, py: Python, suffix: &str) -> PyResult<PyLogger> {
        let logger_name = if slf.fast_logger.name.is_empty() {
            suffix.to_string()
        } else {
            format!("{}.{}", slf.fast_logger.name, suffix)
        };
        crate::globals::get_logger(py, Some(&logger_name), None)
    }

    #[pyo3(signature = (level))]
    fn isEnabledFor(&self, level: u32) -> PyResult<bool> {
        Ok(self
            .fast_logger
            .is_enabled_for(LogLevel::from_usize(level as usize)))
    }
}
