$(document).ready(function() {
    console.log("ready");
    $('video').width($(document).width());
    $(window).resize(function() {
        $('video').width($(document).width());
    });
    $('video').acornMediaPlayer({
		theme: 'darkglass',
		volumeSlider: 'vertical'
	});
});
