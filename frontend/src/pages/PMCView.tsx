export function PMCView() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Performance Management Chart</h1>
      <p className="text-gray-600 dark:text-gray-400">
        CTL/ATL/TSB chart tracking fitness and fatigue over time.
      </p>
      <div className="mt-6 h-96 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 flex items-center justify-center">
        <span className="text-gray-400 dark:text-gray-500">PMC chart will render here</span>
      </div>
    </div>
  );
}
