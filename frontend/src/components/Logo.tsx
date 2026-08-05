interface LogoProps {
  size?: "sm" | "md" | "lg";
  showText?: boolean;
}

export function Logo({ size = "md", showText = true }: LogoProps) {
  const sizeClasses = {
    sm: "w-6 h-6",
    md: "w-8 h-8", 
    lg: "w-10 h-10",
  };

  const textSizeClasses = {
    sm: "text-sm",
    md: "text-lg",
    lg: "text-xl",
  };

  return (
    <div className="flex items-center gap-2">
      <svg 
        className={sizeClasses[size]} 
        viewBox="0 0 32 32" 
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Background circle - uses primary color from theme */}
        <circle cx="16" cy="16" r="15" className="fill-primary"/>
        {/* Power curve shape */}
        <path 
          d="M6 10 Q8 8, 12 12 Q16 16, 20 14 Q24 12, 26 18" 
          className="stroke-primary-foreground"
          strokeWidth="3" 
          strokeLinecap="round"
          fill="none"
        />
        {/* Peak dot */}
        <circle cx="8" cy="9" r="2" className="fill-primary-foreground"/>
      </svg>
      {showText && (
        <span className={`font-bold text-foreground ${textSizeClasses[size]}`}>
          TrainDash
        </span>
      )}
    </div>
  );
}
