/**
 * Primitives Barrel Export
 *
 * THE SWAP LAYER: Import all UI components from here.
 * When you want to use a new library (MagicUI, motion-primitives, etc.),
 * change the export source here — all consumers update automatically.
 *
 * @see /frontend/import-ui.md for detailed guide
 */

// ============================================================================
// UI Components (shadcn base - swap these when importing new libraries)
// ============================================================================
export { Button, buttonVariants } from "@/components/ui/button";
export { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
export { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
export { Badge } from "@/components/ui/badge";
export { Skeleton } from "@/components/ui/skeleton";
export { Input } from "@/components/ui/input";
export { Label } from "@/components/ui/label";
export { Textarea } from "@/components/ui/textarea";
export { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
export { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
export { StatusBadge } from "@/components/ui/status-badge";
export { MarkdownContent } from "@/components/ui/markdown-content";
export { ExpandableScreen, ExpandableScreenTrigger, ExpandableScreenContent } from "@/components/ui/expandable-screen";

// ============================================================================
// Motion Primitives (custom - our reusable animation components)
// ============================================================================
export { FadeIn } from "./motion/FadeIn";
export { StaggerList, StaggerItem } from "./motion/StaggerList";
export { StatusTransition } from "./motion/StatusTransition";

// External motion primitives (from npm packages)
export { ScrollProgress } from "@/components/motion-primitives/scroll-progress";
