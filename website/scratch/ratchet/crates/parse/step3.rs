//! Parsing.

use core::num::ParseIntError;

/// Parse a port.
///
/// # Errors
/// Returns the parse error for text that is not a port number.
pub fn port(text: &str) -> Result<u16, ParseIntError> {
    text.parse()
}
