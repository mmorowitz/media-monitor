# TODO: Code Improvements

## Overview
Plan to implement 4 code quality improvements, one at a time with separate commits. Goal: concise, readable code with low duplication.

## 1. Create Base MediaClient Class ✅
**Status**: Completed  
**Problem**: Reddit and YouTube clients have ~30 lines of duplicated code (category handling, common patterns)  
**Solution**: Extract common functionality into `BaseMediaClient` abstract class  
**Benefits**: 
- Eliminate code duplication
- Cleaner inheritance pattern  
- Easier to add new sources
- More maintainable

**Implementation Plan**:
- [x] Create `src/base_client.py` with `BaseMediaClient` abstract class
- [x] Extract common category/simple format handling in `__init__`
- [x] Extract category mapping logic in `get_new_items_since`
- [x] Add abstract methods for source-specific behavior
- [x] Refactor `reddit_client.py` to inherit from base class
- [x] Refactor `youtube_client.py` to inherit from base class
- [x] Update tests to ensure no regressions
- [x] Commit: "refactor: add base media client class"

## 2. Split Email Formatting from Sending ⏳
**Status**: Next to implement  
**Problem**: `send_email()` function violates single responsibility - formats AND sends  
**Solution**: Extract `format_email_content()` function and separate HTML template  
**Benefits**:
- Better separation of concerns
- Email formatting becomes reusable
- More testable components
- Complete separation of presentation from logic
- Non-developers can modify email layout without touching code
- Template can be version controlled separately

**Implementation Plan**:
- [ ] Create `templates/email_template.html` with placeholder variables
- [ ] Create `format_email_content(all_items)` function using template
- [ ] Extract body/HTML generation logic from `send_email()`
- [ ] Update `send_email()` to use new formatting function
- [ ] Add templating engine dependency (Jinja2 or simple substitution)
- [ ] Add tests for email formatting separately from sending
- [ ] Commit: "refactor: separate email formatting with template"

## 3. Add Configuration Validation ⏸️
**Status**: Planned  
**Problem**: Config accessed directly without validation, potential runtime errors  
**Solution**: Add `validate_config()` function with helpful error messages  
**Benefits**:
- More robust application
- Better user experience with clear error messages
- Catch config issues early

**Implementation Plan**:
- [ ] Create `validate_config(config)` function in main.py
- [ ] Add validation for required fields (API keys, credentials)
- [ ] Add validation for config structure (categories vs simple format)
- [ ] Provide helpful error messages for common mistakes
- [ ] Call validation after `load_config()` in main()
- [ ] Add tests for various config validation scenarios
- [ ] Commit: "feat: add configuration validation"

## 4. Extract Database Abstraction ⏸️
**Status**: Planned  
**Problem**: Database operations scattered between main.py and db.py  
**Solution**: Create `MediaDatabase` class encapsulating all database operations  
**Benefits**:
- Cleaner separation of concerns
- Easier to modify database behavior
- More object-oriented approach

**Implementation Plan**:
- [ ] Create `MediaDatabase` class in `src/db.py`
- [ ] Move database operations into class methods
- [ ] Add context manager support for connection handling
- [ ] Update main.py to use database class instead of functions
- [ ] Update tests to work with new database abstraction
- [ ] Commit: "refactor: extract database abstraction"

## Notes
- Each improvement should be implemented and committed separately
- Run full test suite after each change to ensure no regressions
- Maintain backward compatibility throughout
- Focus on keeping code concise and readable