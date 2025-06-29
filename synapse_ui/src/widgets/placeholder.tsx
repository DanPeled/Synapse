export function Placeholder({ text = "Coming soon...", className = "" }) {
  return (
    <div className={`p-4 border-2 border-dashed border-gray-500 rounded-md text-sm text-gray-400 text-center ${className} w-full h-full`}>
      {text}
    </div>
  );
}
