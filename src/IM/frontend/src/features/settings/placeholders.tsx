export function PlaceholderBlock(props: { title: string; description: string }) {
  return (
    <div>
      <h2 className="im-title text-xl font-bold">{props.title}</h2>
      <p className="mt-2 text-sm text-slate-500">{props.description}</p>
    </div>
  );
}
