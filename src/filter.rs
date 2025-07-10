pub trait Filter: Send + Sync {
    /// Determines if the log record should be processed.
    ///
    /// # Arguments
    ///
    /// * `record` - A reference to the log record to be filtered.
    ///
    /// # Returns
    ///
    /// * `true` if the record should be processed, `false` otherwise.
    fn filter(&self, record: &crate::core::LogRecord) -> bool;
}

// Example of a simple filter that always returns true
pub struct AllowAllFilter;

impl Filter for AllowAllFilter {
    fn filter(&self, _record: &crate::core::LogRecord) -> bool {
        true
    }
}
