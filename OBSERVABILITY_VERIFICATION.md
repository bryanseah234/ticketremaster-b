# Sentry & PostHog Verification Guide

## Frontend (Vercel Deployment)

### Sentry Configuration Check

1. **Verify environment variables in Vercel:**
   - Go to Vercel Project → Settings → Environment Variables
   - Confirm these are set:
     - `VITE_SENTRY_DSN=https://b530843eb471a229d484d6843bae8e0f@o4511024427761664.ingest.us.sentry.io/4511128530124800`
     - `VITE_SENTRY_ENVIRONMENT=production` (or your actual environment)
     - `VITE_SENTRY_RELEASE=1.0.0` (or your git commit hash)

2. **Test locally:**
   ```bash
   cd ticketremaster-f
   npm run build
   npm run preview
   ```
   Then trigger an error in the browser console:
   ```javascript
   throw new Error('Test Sentry error')
   ```

3. **Check Sentry dashboard:**
   - Go to https://sentry.io/
   - Select your project
   - Look for "Issues" tab
   - You should see the test error within a few seconds

### PostHog Configuration Check

1. **Verify environment variables in Vercel:**
   - `VITE_POSTHOG_API_KEY=phc_VZDGAgXbUfcF8t3FFwPzx6ifo8uktsrJ6zrRfxOuY5H`
   - `VITE_POSTHOG_HOST=https://us.i.posthog.com`

2. **Test locally:**
   ```bash
   cd ticketremaster-f
   npm run dev
   ```
   Then check browser console for PostHog initialization:
   ```javascript
   // In browser console
   console.log(posthog.get_distinct_id())
   ```

3. **Check PostHog dashboard:**
   - Go to https://us.posthog.com/project/361191
   - Navigate to "Activity" or "Live events"
   - You should see pageview events

### Common Issues

**No data appearing in Sentry:**
1. Check browser console for Sentry errors
2. Verify DSN is correct (no typos)
3. Check if ad blockers are blocking Sentry
4. Verify `tracesSampleRate` is > 0

**No data appearing in PostHog:**
1. Check browser console for PostHog errors
2. Verify API key is correct
3. Check if `disable_session_recording` is blocking events
4. Verify `api_host` is reachable

## Backend (Kubernetes/Docker)

### Sentry Configuration Check

1. **Verify environment variables:**
   ```bash
   # In your K8s pod or Docker container
   echo $SENTRY_DSN
   echo $SENTRY_ENVIRONMENT
   ```

2. **Test from backend:**
   ```python
   # In any service
   import sentry_sdk
   sentry_sdk.capture_message("Test Sentry message from backend")
   ```

3. **Check Sentry dashboard:**
   - Look for backend errors in your Sentry project
   - Filter by environment (development/production)

### Common Backend Issues

**sentry-sdk not installed:**
- Make sure `pip install -r shared/requirements.txt` was run
- Check `urllib3` is installed (required by sentry-sdk)

**DSN not set:**
- Verify `.env` file has `SENTRY_DSN` set
- In Docker/K8s, ensure env vars are passed correctly

## Debugging Steps

### 1. Frontend Build Test
```bash
cd ticketremaster-f
npm run build
# Check for build errors
```

### 2. Environment Variable Injection Test
In Vercel, after deployment:
- Open browser DevTools → Console
- Type: `import.meta.env` (in Vite apps, use `import.meta.env` in code)
- Or check Network tab for API calls to see if env vars are being used

### 3. Sentry Test Event
Add this to a component's mounted hook temporarily:
```typescript
import * as Sentry from '@sentry/vue'

onMounted(() => {
  Sentry.captureMessage('Test message from TicketRemaster')
})
```

### 4. PostHog Test Event
```typescript
import posthog from 'posthog-js'

onMounted(() => {
  posthog.capture('test_event', { source: 'frontend_test' })
})
```

### 5. Backend Test
SSH into a pod or run locally:
```python
import os
import sentry_sdk

print(f"SENTRY_DSN: {os.getenv('SENTRY_DSN', 'NOT SET')}")
sentry_sdk.init(dsn=os.getenv('SENTRY_DSN'))
sentry_sdk.capture_message("Backend test message")
```

## Expected Behavior

### Frontend
- Errors are automatically captured by Sentry
- Page views are captured by PostHog
- Session replays are recorded (if enabled)
- Performance traces are captured

### Backend
- Unhandled exceptions are captured
- Performance monitoring for database queries
- Breadcrumb logging for HTTP requests

## If Still Not Working

1. **Check Sentry project URL:** Make sure you're looking at the correct Sentry project
2. **Check PostHog project ID:** Your project ID is 361191
3. **Check environment filters:** Both dashboards have environment filters - make sure you're viewing the right environment
4. **Check rate limits:** Free tiers have limits, but test events should still appear
5. **Check network/firewall:** Ensure your deployment can reach Sentry/PostHog endpoints

## Contact Information

- Sentry Support: https://sentry.io/support/
- PostHog Support: https://posthog.com/docs/chat-with-ai
