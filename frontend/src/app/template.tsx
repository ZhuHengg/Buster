// A template (unlike a layout) is re-created on every navigation, so each tab opens with the entrance animation.
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="page-enter flex min-h-0 min-w-0 flex-1 flex-col">{children}</div>;
}
