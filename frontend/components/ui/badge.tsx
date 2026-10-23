import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "cn";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border-2 border-ink px-2.5 py-0.5 text-xs font-bold whitespace-nowrap",
  {
    variants: {
      variant: {
        default: "bg-duck text-ink",
        beak: "bg-beak text-ink",
        outline: "bg-paper text-ink",
        low: "bg-paper text-ink",
        medium: "bg-duck-soft text-ink",
        high: "bg-beak text-ink",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

function Badge({
  className,
  variant,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span data-slot="badge" className={cn(badgeVariants({ variant, className }))} {...props} />;
}

export { Badge, badgeVariants };
