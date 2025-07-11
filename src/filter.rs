//! # Log Filters
//!
//! This module provides filtering capabilities for log records. Filters allow
//! fine-grained control over which log records are processed by handlers,
//! beyond simple level-based filtering.
//!
//! ## Filter Types
//!
//! - **AllowAllFilter**: Pass-through filter that accepts all records
//!
//! ## Custom Filters
//!
//! Custom filters can be implemented by creating types that implement the
//! Filter trait. Common use cases include:
//!
//! - Filtering by logger name patterns
//! - Filtering by message content
//! - Rate limiting based on record frequency
//! - Conditional filtering based on context
//!
//! ## Performance
//!
//! Filters are called for every log record that passes level checks,
//! so implementations should be efficient. Complex filtering logic
//! should be optimized for the common case.

/// Trait for filtering log records based on custom criteria.
///
/// Filters provide a way to selectively process log records beyond
/// simple level-based filtering. They can examine any aspect of a
/// log record to make filtering decisions.
///
/// # Thread Safety
///
/// All filters must be thread-safe (Send + Sync) as they may be
/// used concurrently from multiple threads.
///
/// # Performance Considerations
///
/// - Filters are called for every log record
/// - Keep filtering logic lightweight
/// - Consider caching expensive computations
/// - Return early for common cases
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

/// Simple filter that allows all log records to pass through.
///
/// This filter always returns true, effectively disabling filtering.
/// It's useful as a default filter or for testing scenarios where
/// you want to ensure all records are processed.
///
/// # Use Cases
///
/// - Default filter when no filtering is needed
/// - Testing and debugging scenarios
/// - Placeholder filter during development
pub struct AllowAllFilter;

/// Implementation of Filter trait for AllowAllFilter.
///
/// Always returns true, allowing all records to pass through.
impl Filter for AllowAllFilter {
    /// Allow all log records to pass through the filter.
    ///
    /// # Arguments
    ///
    /// * `_record` - The log record to filter (ignored)
    ///
    /// # Returns
    ///
    /// Always returns `true`
    fn filter(&self, _record: &crate::core::LogRecord) -> bool {
        true
    }
}
