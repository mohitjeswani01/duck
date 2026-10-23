import { cn } from "cn";

interface ChipProps extends React.ComponentProps<"button"> {
  active?: boolean;
}

/** Clickable pill — bug symptom chips on the landing page, evidence
 * file:line chips in the hypothesis card. Neo-brutalist press on click. */
function Chip({ className, active, ...props }: ChipProps) {
  return (
    <button
      type="button"
      data-slot="chip"
      className={cn(
        "press-down inline-flex items-center gap-1.5 rounded-full border-2 border-ink bg-paper px-3.5 py-2 text-left text-sm font-medium text-ink shadow-brutal-sm transition-colors hover:bg-duck-soft disabled:pointer-events-none disabled:opacity-50",
        active && "bg-duck",
        className
      )}
      {...props}
    />
  );
}

export { Chip };
