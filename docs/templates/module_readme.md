# [Module Name]

## Purpose

One-paragraph description of what this module does and why it exists within the sports betting project. Explain the specific problem it solves and how it fits into the overall architecture.

## Quick Start

```python
# 2-3 line example of most common usage
from [module].[submodule] import [MainClass]

# Example usage
instance = [MainClass](param=value)
result = instance.main_method()
```

## Installation

Any module-specific dependencies:

```bash
pip install -r requirements.txt  # Already includes this module's deps
```

## Components

### [Component 1: Main Class/Function]

**Purpose**: Brief description of what this component does

**Usage**:

```python
from [module] import [Component]

# Example with explanation
component = [Component](initialization_params)
output = component.process(input_data)
```

**Parameters**:

- `param1` (type): Description
- `param2` (type, optional): Description (default: value)

**Returns**:

- `type`: Description of return value

**Gotchas**:

- Common pitfall 1: How to avoid
- Data leakage risk: When to use `.shift(1)`

### [Component 2: Helper Functions]

**Purpose**: Supporting utilities for the main component

**Available Functions**:

- `function1(args)`: Brief description
- `function2(args)`: Brief description

## Architecture Decisions

This module implements the following design decisions:

- **[ADR-XXX: Decision Title](../DECISIONS.md#adr-xxx)** — Why this approach was chosen
- **[ADR-YYY: Another Decision](../DECISIONS.md#adr-yyy)** — Technical rationale

## Common Patterns

### Pattern 1: When to Use X Over Y

```python
# Good: Use X when condition A
if condition_a:
    use_x()

# Bad: Don't use Y for condition A
# Reason: explain why
```

### Pattern 2: Data Leakage Prevention

```python
# Always shift rolling calculations to prevent look-ahead bias
rolling_avg = df['points'].rolling(window=5).mean().shift(1)

# ❌ WRONG: This leaks future data
# rolling_avg = df['points'].rolling(window=5).mean()
```

### Pattern 3: [Domain-Specific Best Practice]

Explain sports betting or modeling best practice specific to this module.

## Testing

Run tests for this module:

```bash
# All tests
make test

# Module-specific tests
pytest tests/test_[module_name].py -v

# With coverage
pytest tests/test_[module_name].py --cov=[module] --cov-report=html
```

## Performance Considerations

- **Speed**: Expected runtime characteristics
- **Memory**: Typical memory usage
- **Scaling**: How this performs with large datasets (e.g., 10,000+ games)

## Examples

### Example 1: [Common Use Case]

```python
"""
Description of what this example demonstrates
"""
# Code example with comments
```

### Example 2: [Advanced Use Case]

```python
"""
Description of advanced scenario
"""
# More complex code example
```

## Error Handling

Common errors and how to resolve them:

```python
# Error: [Common Error Message]
# Solution: [How to fix it]
```

## References

### Related Modules

- `[other_module]` — How they interact
- `[dependency_module]` — What this module depends on

### External Documentation

- [Library/API Name](https://url) — Relevant external docs
- Domain knowledge in [CLAUDE.md](../../CLAUDE.md#section)

## Contributing

When modifying this module:

1. **Update docstrings** for any changed functions
2. **Add tests** for new functionality
3. **Update this README** if structure changes
4. **Consider ADR** for architectural changes
5. **Check for data leakage** in any new calculations

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-01-XX | Initial implementation |

## Troubleshooting

### Issue 1: [Common Problem]

**Symptom**: What the user experiences

**Cause**: Why this happens

**Solution**:

```python
# How to fix it
```

### Issue 2: [Performance Degradation]

**Symptom**: Slow performance with large datasets

**Solution**: Use these optimization techniques...

---

**Maintained by**: [Agent/Role]
**Last Updated**: 2026-01-24
**Status**: ✅ Active | ⚠️ Experimental | 🔄 Refactoring | 🗃️ Deprecated
