//! Parsing.

/// Parse a port.
#[must_use]
pub fn port(text: &str) -> u16 {
    text.parse().unwrap()
}

/// Parse a count.
#[must_use]
pub fn count(text: &str) -> u32 {
    text.parse().unwrap()
}
