### Task 9: Run Extension in Visual Studio Code

**Files:**
- Modify: `package.json` (verify correct module/type configuration)
- Verify: `tsconfig.json` (correct output path)

**Interfaces:**
- Consumes: All previous components (compiled output, VS Code)
- Produces: A running extension in VS Code Extension Development Host

- [ ] **Step 1: Verify package.json configuration**

Ensure the entry point and module type are correct:

```json
{
  "main": "./out/extension.js",
  "type": "module"
}
```

These must match your tsconfig output directory and ES module compilation.

- [ ] **Step 2: Verify tsconfig.json**

Ensure the compiled output path matches `package.json`:

```json
{
  "compilerOptions": {
    "outDir": "./out",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "rootDir": "./src",
    "target": "ES2022"
  },
  "include": ["src/**/*"]
}
```

- [ ] **Step 3: Compile the project**

Run: `npm run compile`
Expected: No TypeScript errors, `out/extension.js` created

- [ ] **Step 4: Launch extension in VS Code**

There are two ways:

**Option A: From VS Code (recommended)**
1. Open the project root in VS Code
2. Press **F5** (or go to Run → Start Debugging)
3. This launches a new "Extension Development Host" window with your extension loaded

**Option B: From command line**
```bash
code --extensionDevelopmentPath=C:/gh/gamify_ai
```
Then in the new window, go to Extensions and reload/reinstall the extension.

- [ ] **Step 5: Verify extension works**

In the Extension Development Host window:
1. Open Command Palette (**Ctrl+Shift+P**)
2. Run `Gamify AI: Show Gamepad Debug Info`
3. Check the "Gamify AI Debug" output channel appears with module list

- [ ] **Step 6: Test gamepad (if available)**

If you have a gamepad connected:
1. Connect your gamepad
2. Run the extension
3. Press buttons to see if actions fire (no visible feedback yet without full integration)

- [ ] **Step 7: Update progress.md**

Mark Task 9 as complete in the progress tracker.

- [ ] **Step 8: Commit**

```bash
git add package.json tsconfig.json .superpowers/sdd/2026-09-17-gamify-ai/task-9-brief.md
git commit -m "docs: add task brief for running extension in VS Code"
```

---
