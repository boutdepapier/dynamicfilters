(function($) {
		$(document).ready(function($) {
        	if ($('form').length > 1) {
        		var form = $('form[name=filters]');
        	}
        	else {
        		var form = $('form');
        	}
        	$('.add_adminfilters').click(function(){
				form.submit();
	       	});
	       	$('.load_adminfilters').click(function(){
				form.submit();
	       	});
	       	$('input[name=save_button]').click(function(){
	       		$('.save_adminfilters').val(1);
	       		form.submit();
	       	});
	       	$('input[name=add_button]').click(function() {
	       		location.href = 'add_filter/'
	       	});
	       	$('#header_toggle').click(function(){
	       		$('#custom_filters_header').toggle();
	       		if ($('#custom_filters_header').css('display') == 'none') {
	       			$(this).text('show');
	       			$.cookie(cookie_name, false);
	       		}
	       		else {
	       			$(this).text('hide');
	       			$.cookie(cookie_name, true);
	       		}
	       	});
	       	$('.enable').click(function(){
	       		var enabled = $(this).attr('checked');
	       		var enable_name = $(this).attr('name');
	       		var field_name = enable_name.substr(0, enable_name.indexOf('_enabled'));
	       		if (enabled) {
	       			$('#'+field_name+'_criteria_container').show();
	       		}
	       		else {
	       			$('#'+field_name+'_criteria_container').hide();
	       		}
	       	});
	       	$('select.value').each(function(){
	       		if ($(this).find('option').length > 1) {
	       			var name = $(this).attr('name');
	       			var fname = name.substr(0, name.indexOf('_value'));
	       			$(this).after(' <a href="javascript:expand_choices(\''+fname+'\');" id="'+fname+'_toggle">expand</a>');
	       		}
	       	});
	       	$('.dcontainer').each(function() {
	       		$(this).find('p').css('float', 'left');
	       	});

	       	$('.criteria').change(function() {
	       		var fvalue = $(this).attr('name');
	       		var fname = fvalue.substr(0, fvalue.indexOf('_criteria'));
	       		reset_containers(fname);
	       		if ($(this).val() == 'between') {
	       			$('#'+fname+'_dcontainer').show();
	       			$('#'+fname+'_dcontainer').find('p').show();
	       			$('#'+fname+'_dcontainer').find('input').show();
	       			$('#'+fname+'_dcontainer').find('span').show();
	       			$('input[name='+fname+'_dago]').hide();
	       			$('#'+fname+'_value_container').hide();
	       		}
	       		else if ($.inArray($(this).val(), ['today', 'this_week', 'this_month', 'this_year']) >= 0) {
	       			$('#'+fname+'_value_container').hide();
	       		}
	       		else if ($(this).val() == 'days_ago') {
	       			$('#'+fname+'_dcontainer').show();
	       			$('#'+fname+'_dcontainer').find('p').hide();
	       			$('#'+fname+'_dcontainer').find('input').hide();
	       			$('#'+fname+'_dcontainer').find('span').hide();
	       			$('#'+fname+'_value_container').hide();
	       			$('input[name='+fname+'_dago]').show();
	       		}

	       	});
	       	$('.criteria').each(function(){
	       		if ($.inArray($(this).val(), ['today', 'this_week', 'this_month', 'this_year', 'days_ago', 'between']) >= 0) {
	       			$(this).trigger('change');
	       		}
	       	});
    	});
	})(django.jQuery);
	function expand_choices(field_name) {
		$('select[name='+field_name+'_value]').attr('multiple', 'multiple');
		$('#'+field_name+'_toggle').html('<a href="javascript:reduce_choices(\''+field_name+'\')">reduce</a>');
	}
	function reduce_choices(field_name) {
		$('select[name='+field_name+'_value]').removeAttr('multiple');
		$('#'+field_name+'_toggle').html('<a href="javascript:expand_choices(\''+field_name+'\')">expand</a>');
	}
	function reset_containers(fname) {
		$('#'+fname+'_value_container').show();
		$('#'+fname+'_dcontainer').hide();
	}
	function load_header_visibility() {
		if (typeof($.cookie(cookie_name)) == 'undefined') {
			$.cookie(cookie_name, true);
		}
		else {
			var header_visible = $.cookie(cookie_name);
			if (header_visible == 'false') {
				$('#custom_filters_header').hide();
				$('#header_toggle').text('show');
			}
		}
	}
	function delete_filter(filter_name) {
		if (confirm('Are you sure you want to delete current custom filter "'+filter_name+'"')) {
			location.href = $('.deletefilter').attr('href');
		}
		return false;
	}
