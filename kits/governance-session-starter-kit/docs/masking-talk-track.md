# Talk track: masking without breaking downstream (60 seconds)

Presenter notes for the Day 2 governance recap. Frame: **governance worked, here is how we keep
downstream moving.** Pairs with `masking-and-downstream-impact.html`.

---

## The 60-second script

> Yesterday the governance team did exactly the right thing. They classified the protected data,
> tagged the columns, and put a mask on the patient identifier so researchers cannot see it. That is
> the control we want.
>
> Here is what we all learned. That identifier, `person_id`, is the key every table joins on. The mask
> returned NULL, and a join on NULL matches nothing, so the models downstream quietly went to zero rows.
> No error. Just no data. The mask did its job. We just learned that masking a join key is a downstream
> event for every team reading it.
>
> The fix is small. For a key that others join on, we return a stable token instead of NULL. Same
> patient always gets the same token, so joins still line up, and nobody ever sees the real id. Privacy
> and joinability at the same time.
>
> The second thing we hit is real platform behavior, not a mistake. A mask function has to return the
> column's own data type. Our PII tag sat on a number column and a text column, so one function could
> not cover both. The answer is a small library of mask functions, one per data type, bound to the tag
> once. Classify once, and the policy follows the tag to every new table. That is the scale we wanted.

---

## Four beats (if you have less time)

1. **Governance worked.** Classify, tag, mask. The control is correct and we keep it.
2. **A masked join key stops everyone reading it.** `person_id` to NULL zeroed the downstream joins, silently.
3. **Tokenize keys, do not nullify them.** A stable hash keeps joins working and never reveals the real id.
4. **One tag can need several functions.** Return type must match the column type; a small typed function library plus tag policies scales it.

---

## If asked

- **"So was masking a mistake?"** No. Masking the identifier is the requirement. The lesson is which
  mask style to use on a key, and to sequence and announce a policy that lands on shared data.
- **"Does the token let them re-identify patients?"** No. It is a one-way hash. It is only useful for
  matching rows to each other, never for recovering the real id.
- **"Why not just exempt the pipeline?"** That works when the job is cleared to see real ids. Tokens are
  the safer default, because they hold even when you are unsure who will read the data later.
- **"Is the tag policy available here?"** Attribute-based access control policies are generally
  available, but can be feature-gated per workspace. The per-table masks deliver the same protection
  today; the tag policy is the pattern to adopt as it turns on.
