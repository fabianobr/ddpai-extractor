(function (root) {
    function parseUtc(ts) {
        if (!ts) return null;
        // Check if string ends with timezone designator
        const tzMatch = ts.match(/(Z|[+-]\d{2}:?\d{2})$/i);
        if (tzMatch) {
            const d = new Date(ts);
            return isNaN(d.getTime()) ? null : d.getTime();
        } else {
            // No timezone, treat as UTC
            const d = new Date(ts + 'Z');
            return isNaN(d.getTime()) ? null : d.getTime();
        }
    }

    function elapsedAt(trip, i) {
        const point = trip.points[i];
        if (point.length >= 6 && typeof point[5] === 'number') {
            return point[5];
        } else {
            const n = trip.points.length;
            if (n <= 1) return 0;
            const duration = trip.duration_min * 60;
            return Math.round(i / (n - 1) * duration);
        }
    }

    function wallClockAt(trip, i) {
        const start = parseUtc(trip.start_timestamp);
        if (start === null) return null;
        return start + elapsedAt(trip, i) * 1000;
    }

    function formatClock(ms, timeZone) {
        if (ms === null || ms === undefined) return '--:--:--';
        const options = { timeZone, hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' };
        if (timeZone === undefined) delete options.timeZone;
        return new Intl.DateTimeFormat('pt-BR', options).format(new Date(ms));
    }

    function formatDuration(seconds) {
        if (seconds < 60) return `${Math.floor(seconds)} s`;
        
        const totalMinutes = Math.round(seconds / 60);
        const hours = Math.floor(totalMinutes / 60);
        const minutes = totalMinutes % 60;
        
        if (hours >= 1 && minutes === 0) {
            return `${hours} h`;
        } else if (hours >= 1) {
            return `${hours} h ${minutes} min`;
        } else {
            return `${minutes} min`;
        }
    }

    function tripTitle(trip, timeZone) {
        const start = parseUtc(trip.start_timestamp);
        if (start === null) return trip.label;

        const date = new Date(start);
        const weekday = new Intl.DateTimeFormat('pt-BR', { weekday: 'long', timeZone }).format(date);
        const hour = Number(new Intl.DateTimeFormat('en-US', { hour: 'numeric', hourCycle: 'h23', timeZone }).format(date));
        
        let period;
        if (hour >= 0 && hour < 5) {
            period = 'de madrugada';
        } else if (hour >= 5 && hour < 12) {
            period = 'de manhã';
        } else if (hour >= 12 && hour < 18) {
            period = 'à tarde';
        } else {
            period = 'à noite';
        }
        
        const weekdayCapitalized = weekday.charAt(0).toUpperCase() + weekday.slice(1);
        return `${weekdayCapitalized} ${period}`;
    }

    function indexAtElapsed(trip, seconds) {
        const points = trip.points;
        if (points.length === 0) return -1;
        
        // Check if we have time offsets
        const hasOffsets = points[0].length >= 6 && typeof points[0][5] === 'number';
        
        if (hasOffsets) {
            // Binary search for the last offset <= seconds
            let left = 0;
            let right = points.length - 1;
            let result = 0;
            
            while (left <= right) {
                const mid = Math.floor((left + right) / 2);
                if (points[mid][5] <= seconds) {
                    result = mid;
                    left = mid + 1;
                } else {
                    right = mid - 1;
                }
            }
            
            return Math.min(result, points.length - 1);
        } else {
            // Use proportional approach
            const n = points.length;
            if (n <= 1) return 0;
            const duration = trip.duration_min * 60;
            const index = duration > 0 ? Math.round(seconds / duration * (n - 1)) : 0;
            return Math.max(0, Math.min(index, n - 1));
        }
    }

    const api = {
        parseUtc,
        elapsedAt,
        wallClockAt,
        formatClock,
        formatDuration,
        tripTitle,
        indexAtElapsed
    };
    
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.TripModel = api;
})(typeof window === 'undefined' ? globalThis : window);
