/* Keep paired camera players aligned without recursively responding to our own actions. */
(function (root) {
    function pointAtVideoTime(group, camera, seconds, tolerance) {
        const offsets = group && group.video_sync && group.video_sync[camera];
        if (!Array.isArray(offsets) || !Number.isFinite(seconds)) return null;
        let closest = null, distance = Infinity;
        offsets.forEach(function (value, index) {
            if (!Number.isFinite(value)) return;
            const difference = Math.abs(value - seconds);
            if (difference < distance) { closest = index; distance = difference; }
        });
        return distance <= (tolerance === undefined ? 2 : tolerance) ? closest : null;
    }
    function timeForPoint(group, camera, index) {
        const offsets = group && group.video_sync && group.video_sync[camera];
        const value = offsets && offsets[index];
        return Number.isFinite(value) && value >= 0 ? value : null;
    }
    /* Aviso de confiança da calibração do relógio; '' se não houver o campo (JSON antigo) ou a confiança for alta. */
    function syncConfidenceWarning(videoSync) {
        const confidence = videoSync && videoSync.confidence;
        if (confidence === 'low') return 'A posição no mapa pode não coincidir com o vídeo.';
        if (confidence !== 'medium') return '';
        const spread = Number.isFinite(videoSync.offset_typical_spread_s) ? videoSync.offset_typical_spread_s : videoSync.offset_spread_s;
        return Number.isFinite(spread) ? 'Sincronização aproximada (±' + Math.max(1, Math.ceil(spread)) + ' s)' : 'Sincronização aproximada';
    }
    function linkVideos(rear, front, state, getGroup) {
        let changing = false;
        const pendingPlay = new WeakSet();
        const pendingPause = new WeakSet();
        /* Elementos cujo currentTime foi alterado por este código: o 'seeking' resultante não deve ser re-propagado. */
        const programmaticSeek = new WeakSet();
        function seekTo(video, time) {
            if (Math.abs(video.currentTime - time) <= 0.001) return;  /* sem mudança real pode não haver evento: não marcar */
            programmaticSeek.add(video);
            video.currentTime = time;
        }
        function hasEnded(video) {
            return !!video.ended || (Number.isFinite(video.duration) && video.duration > 0 && video.currentTime >= video.duration - 0.05);
        }
        state.pauseForMissingCoverage = function (video) {
            if (video && !video.paused) { pendingPause.add(video); video.pause(); }
        };
        function correspondingTime(name, otherName, time) {
            const group = getGroup && getGroup();
            if (!group || !group.video_sync) return time;
            const index = pointAtVideoTime(group, name, time);
            return index === null ? null : timeForPoint(group, otherName, index);
        }
        function bind(video, other, name) {
            if (!video) return;
            const otherName = name === 'rear' ? 'front' : 'rear';
            video.addEventListener('play', function () {
                if (pendingPlay.has(video)) { pendingPlay.delete(video); return; }
                if (changing || state.isSyncing) return;
                state.activeVideo = name;
                if (state.mode !== 'linked' || !other || !other.dataset.lazySrc) return;
                const target = correspondingTime(name, otherName, video.currentTime);
                if (target === null) {
                    if (state.onCoverageChange) state.onCoverageChange(otherName, false);
                    if (!other.paused) { pendingPause.add(other); other.pause(); }
                    return;
                }
                if (state.onCoverageChange) state.onCoverageChange(otherName, true);
                changing = true;
                if (!other.hasAttribute('src')) other.src = other.dataset.lazySrc;
                if (Math.abs(other.currentTime - target) > 0.2) seekTo(other, target);
                if (other.paused) {
                    pendingPlay.add(other);
                    const promise = other.play();
                    if (promise && promise.catch) promise.catch(function (error) { pendingPlay.delete(other); console.warn('Não foi possível iniciar a outra câmera:', error); });
                }
                changing = false;
            });
            video.addEventListener('pause', function () {
                if (pendingPause.has(video)) { pendingPause.delete(video); return; }
                if (hasEnded(video)) return;  /* fim natural: o navegador dispara 'pause' antes de 'ended'; a outra câmera segue até o próprio fim */
                if (changing || state.isSyncing || state.mode !== 'linked' || !other || other.paused) return;
                changing = true;
                pendingPause.add(other);
                other.pause();
                changing = false;
            });
            video.addEventListener('seeked', function () { programmaticSeek.delete(video); });
            video.addEventListener('seeking', function () {
                if (programmaticSeek.has(video)) { programmaticSeek.delete(video); return; }
                if (changing || state.isSyncing || state.mode !== 'linked' || !other || !other.dataset.lazySrc) return;
                const target = correspondingTime(name, otherName, video.currentTime);
                if (target === null) {
                    if (state.onCoverageChange) state.onCoverageChange(otherName, false);
                    if (!other.paused) { pendingPause.add(other); other.pause(); }
                    return;
                }
                if (state.onCoverageChange) state.onCoverageChange(otherName, true);
                if (Math.abs(other.currentTime - target) < 0.2) return;
                changing = true;
                if (!other.hasAttribute('src')) other.src = other.dataset.lazySrc;
                seekTo(other, target);
                changing = false;
            });
            video.addEventListener('timeupdate', function () {
                if (changing || state.mode !== 'linked' || state.activeVideo !== name || !other || !other.dataset.lazySrc) return;
                const target = correspondingTime(name, otherName, video.currentTime);
                if (target === null) {
                    if (state.onCoverageChange) state.onCoverageChange(otherName, false);
                    if (!other.paused) { pendingPause.add(other); other.pause(); }
                    return;
                }
                if (state.onCoverageChange) state.onCoverageChange(otherName, true);
                if (!other.hasAttribute('src')) other.src = other.dataset.lazySrc;
                if (Math.abs(other.currentTime - target) > 0.75) seekTo(other, target);
                if (other.paused && !video.paused) {
                    pendingPlay.add(other);
                    const promise = other.play();
                    if (promise && promise.catch) promise.catch(function () { pendingPlay.delete(other); });
                }
            });
        }
        bind(rear, front, 'rear');
        bind(front, rear, 'front');
    }
    if (typeof module !== 'undefined' && module.exports) module.exports = {syncConfidenceWarning: syncConfidenceWarning, linkVideos: linkVideos, pointAtVideoTime: pointAtVideoTime, timeForPoint: timeForPoint};
    else { root.syncConfidenceWarning = syncConfidenceWarning; root.linkVideos = linkVideos; root.pointAtVideoTime = pointAtVideoTime; root.timeForPoint = timeForPoint; }
})(typeof window === 'undefined' ? globalThis : window);
