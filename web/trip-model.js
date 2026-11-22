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

    function cumulativeKm(points) {
        if (!points || points.length === 0) return [];
        
        const R = 6371; // Earth radius in km
        const result = [0];
        
        for (let i = 1; i < points.length; i++) {
            const [lat1, lon1] = points[i - 1];
            const [lat2, lon2] = points[i];
            
            const dLat = (lat2 - lat1) * Math.PI / 180;
            const dLon = (lon2 - lon1) * Math.PI / 180;
            
            const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                      Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                      Math.sin(dLon / 2) * Math.sin(dLon / 2);
            
            const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
            const d = R * c;
            
            result.push(result[i - 1] + d);
        }
        
        return result;
    }

    function downsample(values, n, mode) {
        if (!values || values.length === 0) return [];
        if (n >= values.length) return [...values];
        
        const L = values.length;
        const result = [];
        
        for (let b = 0; b < n; b++) {
            const start = Math.floor(b * L / n);
            const end = Math.max(start + 1, Math.floor((b + 1) * L / n));
            
            if (start >= L) break;
            
            const segment = values.slice(start, end);
            
            if (mode === 'max') {
                result.push(Math.max(...segment));
            } else { // mean
                const sum = segment.reduce((acc, val) => acc + val, 0);
                result.push(sum / segment.length);
            }
        }
        
        return result;
    }

    function routeThumbPath(points, w, h, n) {
        if (!points || points.length === 0) return '';
        
        // Calculate mean latitude for projection
        let sumLat = 0;
        for (const [lat] of points) {
            sumLat += lat;
        }
        const meanLat = sumLat / points.length;
        const meanLatRad = meanLat * Math.PI / 180;
        
        // Equirectangular projection using mean latitude
        const projected = points.map(([lat, lon]) => [
            lon * Math.cos(meanLatRad),
            -lat
        ]);
        
        // Find bounds
        let minX = Infinity, maxX = -Infinity;
        let minY = Infinity, maxY = -Infinity;
        
        for (const [x, y] of projected) {
            minX = Math.min(minX, x);
            maxX = Math.max(maxX, x);
            minY = Math.min(minY, y);
            maxY = Math.max(maxY, y);
        }
        
        // Add margin
        const margin = 4;
        const width = maxX - minX;
        const height = maxY - minY;
        
        // Handle zero dimensions
        let scale;
        if (width === 0 && height === 0) {
            // Single point case
            scale = 1;
        } else if (width === 0) {
            // Vertical line
            scale = (h - 2 * margin) / height;
        } else if (height === 0) {
            // Horizontal line
            scale = (w - 2 * margin) / width;
        } else {
            // Normal case
            scale = Math.min((w - 2 * margin) / width, (h - 2 * margin) / height);
        }
        
        // Center and translate
        const offsetX = (w - scale * width) / 2 - minX * scale;
        const offsetY = (h - scale * height) / 2 - minY * scale;
        
        // Sample points uniformly
        const pathPoints = [];
        const step = (points.length - 1) / (n - 1);
        
        for (let k = 0; k < n; k++) {
            const index = Math.round(k * step);
            const [lat, lon] = points[index];
            const x = lon * Math.cos(meanLatRad);
            const y = -lat;
            const px = Math.round((x * scale + offsetX) * 10) / 10;
            const py = Math.round((y * scale + offsetY) * 10) / 10;
            pathPoints.push(`${k === 0 ? 'M' : 'L'} ${px} ${py}`);
        }
        
        return pathPoints.join(' ');
    }

    function decimalToDms(value, axis) {
        const absolute = Math.abs(value);
        const degrees = Math.floor(absolute);
        const minutesDecimal = (absolute - degrees) * 60;
        const minutes = Math.floor(minutesDecimal);
        const seconds = ((minutesDecimal - minutes) * 60).toFixed(2);
        const hemisphere = axis === 'lat' ? (value >= 0 ? 'N' : 'S') : (value >= 0 ? 'E' : 'W');
        return `${degrees}° ${minutes}' ${seconds}" ${hemisphere}`;
    }

    function buildGpx(points) {
        return '<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="DDpai" xmlns="http://www.topografix.com/GPX/1/1"><trk><name>Trecho DDpai</name><trkseg>' + points.map(p => `<trkpt lat="${p[0]}" lon="${p[1]}"></trkpt>`).join('') + '</trkseg></trk></gpx>';
    }

    function buildKml(points) {
        return '<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><name>Trecho DDpai</name><LineString><coordinates>' + points.map(p => `${p[1]},${p[0]}`).join(' ') + '</coordinates></LineString></Placemark></Document></kml>';
    }

    const api = {
        parseUtc,
        elapsedAt,
        wallClockAt,
        formatClock,
        formatDuration,
        tripTitle,
        indexAtElapsed,
        cumulativeKm,
        downsample,
        routeThumbPath,
        decimalToDms,
        buildGpx,
        buildKml
    };
    
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.TripModel = api;
})(typeof window === 'undefined' ? globalThis : window);
