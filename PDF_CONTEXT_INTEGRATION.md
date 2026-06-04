# PDF Context Display Integration

## Overview
Add "Show PDF Context" button to display which PDF pages/content are being used for question generation (like CLI `--show-context`).

## Changes Required

### 1. Backend Already Complete ✅
- Endpoint exists: `POST /api/v1/context`
- Returns PDF chunks for a given topic

### 2. Frontend API Service ✅
File: `/frontend/services/api.ts`
- Added `getPDFContext()` function

### 3. New Component Created ✅
File: `/frontend/components/PDFContextViewer.tsx`
- Modal dialog to display PDF context
- Shows topic, chunk count, and full context text

### 4. Update GenerationModule.tsx

**Step 1: Update imports (line 2)**
```typescript
import { generateQuestion, getPDFContext } from '../services/api';
import PDFContextViewer from './PDFContextViewer';
```

**Step 2: Add state variables (after line 25)**
```typescript
  const [showContext, setShowContext] = useState(false);
  const [pdfContext, setPdfContext] = useState<{context: string | null, chunks: number} | null>(null);
  const [loadingContext, setLoadingContext] = useState(false);
```

**Step 3: Add handler function (after handleAbort, around line 84)**
```typescript
  const handleShowContext = async () => {
    if (!topic.trim()) return;

    setLoadingContext(true);
    try {
      const ctx = await getPDFContext(topic);
      if (ctx.context) {
        setPdfContext(ctx);
        setShowContext(true);
      } else {
        setError("No PDF context found for this topic.");
      }
    } catch (err: any) {
      setError("Failed to fetch PDF context.");
    } finally {
      setLoadingContext(false);
    }
  };
```

**Step 4: Add "Show Context" button (in the button group around line 153-175)**
```typescript
              <div className="flex items-center gap-2">
                {/* Show Context Button */}
                <button
                  onClick={handleShowContext}
                  disabled={loading || !topic || loadingContext}
                  className={\`
                    p-4 rounded-xl transition-all duration-300 flex-shrink-0
                    \${loading || !topic || loadingContext
                      ? 'bg-warm-100 text-warm-300 cursor-not-allowed'
                      : 'bg-blue-500 text-white hover:bg-blue-600 shadow-lg shadow-blue-500/20'}
                  \`}
                  title="Show PDF Context"
                >
                  {loadingContext ? <Icons.Activity className="w-6 h-6 animate-spin" /> : <Icons.Book className="w-6 h-6" />}
                </button>

                {/* Cancel Button (existing) */}
                {loading && (
                  <button
                    onClick={handleAbort}
                    className="p-4 rounded-xl transition-all duration-300 flex-shrink-0 bg-red-500 text-white hover:bg-red-600 shadow-lg shadow-red-500/20"
                    title="Cancel generation"
                  >
                    <Icons.X className="w-6 h-6" />
                  </button>
                )}

                {/* Generate Button (existing) */}
                <button
                  onClick={() => handleGenerate()}
                  disabled={loading || !topic}
                  className={\`...existing classes...\`}
                >
                  {loading ? <Icons.Activity className="w-6 h-6 animate-spin" /> : <Icons.Zap className="w-6 h-6 fill-current" />}
                </button>
              </div>
```

**Step 5: Add modal at the end of component (before closing </div>, around line 317)**
```typescript
      {/* PDF Context Modal */}
      {showContext && pdfContext && pdfContext.context && (
        <PDFContextViewer
          topic={topic}
          context={pdfContext.context}
          chunks={pdfContext.chunks}
          onClose={() => setShowContext(false)}
        />
      )}
    </div>
  );
};
```

## User Flow

1. User enters a topic (e.g., "information gain")
2. User clicks **📖 Show Context** button (blue book icon)
3. Modal appears showing:
   - Topic name
   - Number of PDF chunks retrieved (e.g., "Retrieved 5 chunks")
   - Full PDF context text
   - "This is the exact context the LLM will use..."
4. User clicks "Close" or X to dismiss
5. User can then generate question with this context

## Benefits

- ✅ Users see exactly what PDF content is being used
- ✅ Helps verify PDF was ingested correctly
- ✅ Transparency into RAG retrieval process
- ✅ Matches CLI `--show-context` functionality
- ✅ No need to regenerate to see context

## Quick Manual Update

Due to file size, here's the quick manual update process:

1. Open `/frontend/components/GenerationModule.tsx`
2. Add imports at top
3. Add 3 state variables after line 25
4. Add `handleShowContext` function after line 84
5. Add blue "Show Context" button in the button group
6. Add modal component at the end

Or I can create the complete file if you prefer!
