# 🧱 UI Component Import Guide

> **One-line swaps. Zero hassle.** This guide explains how to add new UI components from external libraries (MagicUI, motion-primitives, Aceternity, etc.) to this project.

---

## 📖 Why This Exists

When you find a cool component online (like a fancy Dialog from `motion-primitives`), you want to use it everywhere. But if you import it directly in 20 files, swapping it later means changing 20 files.

**The Solution:** We use a "primitives barrel" pattern:

```
Your Component → imports from → @/components/primitives
                                       ↓
                              Re-exports from → @/components/ui/dialog.tsx
                                                OR
                                               motion-primitives (npm)
```

When you swap a library, you change **one file**. Every component using it updates automatically.

---

## 📁 Project Structure

```
frontend/src/components/
├── primitives/              ← THE SWAP LAYER (import from here!)
│   ├── index.ts             ← Main barrel export
│   └── motion/              ← Custom motion components
│       ├── FadeIn.tsx
│       ├── StaggerList.tsx
│       └── StatusTransition.tsx
│
├── ui/                      ← Base components (shadcn style)
│   ├── button.tsx
│   ├── card.tsx
│   ├── dialog.tsx
│   └── ...
│
└── motion-primitives/       ← External library components
    └── scroll-progress.tsx
```

---

## 🚀 How to Add a New Component

### Step 1: Install the Package

```bash
# Example: Adding motion-primitives dialog
npx motion-primitives@latest add dialog

# Or manual npm install
npm install @magic-ui/react
```

### Step 2: Check Where It Landed

Most CLI tools add components to `components/ui/` or a similar folder. Check:
- `frontend/src/components/ui/dialog.tsx` (shadcn style)
- `frontend/src/components/motion-primitives/dialog.tsx` (motion-primitives style)

### Step 3: Add to Primitives Barrel

Open `frontend/src/components/primitives/index.ts` and add the export:

```typescript
// BEFORE: Using local shadcn dialog
export {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
  DialogClose
} from "@/components/ui/dialog";

// AFTER: Swapped to motion-primitives dialog
export {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
  DialogClose
} from "@/components/motion-primitives/dialog";  // ← Changed ONE line
```

### Step 4: Use in Your Component

```tsx
// ✅ CORRECT - Import from primitives (auto-updates when swapped)
import { Dialog, DialogContent, DialogTitle } from "@/components/primitives";

// ❌ WRONG - Direct import (breaks on library swap)
import { Dialog } from "@/components/ui/dialog";
```

---

## 📋 Real Example: Adding motion-primitives Dialog

### 1. Install

```bash
cd frontend
npx motion-primitives@latest add dialog
```

This creates `components/motion-primitives/dialog.tsx` (or similar).

### 2. Update Primitives Barrel

```typescript
// frontend/src/components/primitives/index.ts

// Swap the Dialog export to use motion-primitives
export {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
  DialogClose
} from "@/components/motion-primitives/dialog";
```

### 3. Verify It Works

Any component already importing from `@/components/primitives` will now use the animated version:

```tsx
// This component gets the new Dialog automatically!
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/primitives";

export function MyModal() {
  return (
    <Dialog>
      <DialogTrigger>
        <Button>Open</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>Hello!</DialogTitle>
        <p>This dialog now has motion-primitives animations.</p>
      </DialogContent>
    </Dialog>
  );
}
```

---

## 🎯 Quick Reference: Component Props

### Dialog (motion-primitives style)

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `children` | `ReactNode` | required | Content inside the dialog |
| `variants` | `Variants` | — | Framer Motion animation variants |
| `transition` | `Transition` | — | Framer Motion transition settings |
| `className` | `string` | — | CSS class for styling |
| `defaultOpen` | `boolean` | `false` | Open by default |
| `onOpenChange` | `(open: boolean) => void` | — | Callback when open state changes |
| `open` | `boolean` | — | Controlled open state |

### DialogTrigger

| Prop | Type | Description |
|------|------|-------------|
| `children` | `ReactNode` | Trigger button content |
| `className` | `string` | Styling class |

### DialogContent

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `children` | `ReactNode` | Dialog content |
| `className` | `string` | Styling class |
| `container` | `HTMLElement` | `document.body` | Portal container |

---

## ⚠️ Troubleshooting

### "Component X is not exported"

The new library might use different export names. Check the library docs and update the primitives barrel:

```typescript
// If motion-primitives uses "ModalDialog" instead of "Dialog"
export { ModalDialog as Dialog } from "@/components/motion-primitives/dialog";
```

### Props Are Different

If the new component has different props, you may need a wrapper:

```typescript
// frontend/src/components/primitives/wrappers/DialogWrapper.tsx
import { Dialog as MotionDialog } from "@/components/motion-primitives/dialog";

// Wrapper to match our existing prop interface
export function Dialog({ open, onOpenChange, children, ...props }) {
  return (
    <MotionDialog
      open={open}
      onOpenChange={onOpenChange}
      variants={{ /* your defaults */ }}
      {...props}
    >
      {children}
    </MotionDialog>
  );
}
```

### TypeScript Errors After Swap

Run type-check to find mismatches:

```bash
cd frontend
npm run build  # or: npx tsc --noEmit
```

---

## 📝 Checklist for Adding Components

- [ ] Install package (`npx ...` or `npm install`)
- [ ] Locate the new component file
- [ ] Update `primitives/index.ts` with export
- [ ] Test render on a page
- [ ] Update this doc if new patterns emerge

---

## 🔗 Useful Libraries

| Library | Install Command | Best For |
|---------|----------------|----------|
| [motion-primitives](https://motion-primitives.com) | `npx motion-primitives@latest add <component>` | Animated dialogs, accordions |
| [MagicUI](https://magicui.design) | `npx magicui@latest add <component>` | Hero sections, cards |
| [Aceternity UI](https://ui.aceternity.com) | Copy-paste + adapt | 3D effects, parallax |
| [shadcn/ui](https://ui.shadcn.com) | `npx shadcn-ui@latest add <component>` | Base components |
