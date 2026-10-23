import { cn } from "cn";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex w-full rounded-xl border-2 border-ink bg-paper px-4 py-3 text-base text-ink shadow-brutal placeholder:text-muted-foreground outline-none transition-[box-shadow] focus-visible:shadow-brutal-duck disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  );
}

function Input({ className, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      data-slot="input"
      className={cn(
        "flex h-11 w-full rounded-xl border-2 border-ink bg-paper px-3.5 text-base text-ink shadow-brutal-sm placeholder:text-muted-foreground outline-none transition-[box-shadow] focus-visible:shadow-brutal-duck disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  );
}

export { Textarea, Input };
