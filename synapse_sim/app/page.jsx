import dynamic from 'next/dynamic';

const FieldViewer = dynamic(() => import('@/components/field-viewer'), {
  loading: () => (
    <div className="w-full h-screen bg-neutral-900 flex items-center justify-center">
      <div className="text-white font-mono text-lg">Loading 3D Viewer...</div>
    </div>
  ),
});

export default function Page() {
  return <FieldViewer />;
}
