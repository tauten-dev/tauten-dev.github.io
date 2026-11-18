//! Parsing.

/// Parse a port.
#[must_use]
pub fn port(text: &str) -> u16 {
    text.parse().unwrap()
}
