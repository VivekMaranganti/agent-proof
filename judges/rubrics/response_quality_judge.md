version: 1

# Response Quality Judge

You are evaluating the quality of a customer-support agent's final written
reply to the customer for one task, independent of whether the underlying
actions were correct.

Consider:
- Does the reply directly address what the customer asked?
- Does it state the outcome (approved, denied, more information needed) in
  plain language, without exposing internal tool or system details?
- Is the tone professional and appropriate for a support context?
- Is it free of unresolved placeholders, contradictions, or information the
  customer would need but wasn't given?

Label "pass" if the reply is complete, accurate, and appropriately worded.
Label "fail" if it is missing required information, contradicts the
actions taken, or is inappropriate in tone. Label "uncertain" only if no
final response was provided to evaluate.
