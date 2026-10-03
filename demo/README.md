# Demo: intentionally broken examples
`broken-nextjs/` has one deliberate bug: `page.tsx` imports `@/component/Header` but the folder is `components`.

    errorlens analyze ../samples/vercel_module_not_found.log --repo broken-nextjs
Expected: root cause = module not found, and a verified diff fixing `component` -> `components`.
Every file in `../samples/` is a realistic failing log for one rule.
