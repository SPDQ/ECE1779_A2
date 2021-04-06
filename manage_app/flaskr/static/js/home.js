$(document).ready(function () {

    load_table()
    $('#worker_btn').click(function () {
        worker_chart()
    });

    $('#details_btn').on("click", function () {
        var instances = [];
        $("input[name=instance]:checked").each(function () {
            instances.push($(this).val());
        });
        if (instances.length > 0) {
            details(instances)
        } else {
            $('#charts2').hide();
            $('#charts3').hide();
        }
    });

    $('#refresh_btn').click(function () {
        $('#worker_table').DataTable().ajax.reload();
    });

    $('#add_btn').click(function () {
        add_instance()
    });

    $('#shrink_btn').click(function () {
        delete_instance()
    });

    $('#stop_btn').click(function () {
        stop_manager()
    });

    $('#delete_btn').click(function () {
//        alert("All data cleared successfully!!!");
        clear_data()
    });
    Highcharts.setOptions({
        time: {
            timezone: 'Canada/Eastern'
        }
    });

});

function show_alert(msg, type) {
    if (type == 'alert-warning') {
        title = "Warning: "
    } else if (type == 'alert-success') {
        title = "Success: "
    } else if (type == 'alert-danger') {
        title = "Failure: "
    } else { return '' }

    msg = "<strong>" + title + "</strong>" + msg
    alert = "<div class='alert " + type + " alert-dismissible fade show' role='alert'>" + msg
    alert += "<button type='button' class='close' data-dismiss='alert' aria-label='Close'><span aria-hidden='true'>&times;</span>"
    alert += "</button></div>"
    $('#msg').html(alert)
}

function load_table() {
    $('#worker_table').DataTable({
        ajax: "/fetch_workers",
        "columns": [

            { "data": 'Id' },
            { "data": 'Port' },
            { "data": 'State' },
            {
                sortable: false,
                "render": function (data, type, full, meta) {
                    return '<input type="checkbox" name="instance"' + 'value="' + full.Id + '"/>';
                }
            },
        ],
    });
}

function worker_chart() {
    $.ajax({
        type: 'POST',
        url: '/fetch_healthy_workers',
        data: '',
        contentType: false,
        cache: false,
        processData: false,
        beforeSend: function () {
            $('#chart1').html("<img class='loading' src='static/img/loading.gif'>");
        },
        success: function (data) {
            data = JSON.parse(data);
            data_list = []
            info = JSON.parse(data.data);
            data_list.push({ "data": info })

            var new_chart1 = Highcharts.stockChart('chart1', {
                legend: {
                    enabled: true,
                    align: 'right',
                },

                rangeSelector: {
                    selected: 1
                },

                title: {
                    text: 'Worker number rates in worker pool'
                },

                series: data_list
            });
        },
        error: function (xhr, textStatus, error) {
            $('#chart1').html("");
            show_alert("Unable to show the worker chart ", "alert-danger")
            console.log(error)
        }
    });
}

function details(instance) {
    $.ajax({
        type: 'POST',
        url: '/fetch_cpu_utils',
        data: JSON.stringify(instance),
        contentType: false,
        cache: false,
        processData: false,
        beforeSend: function () {
            $('#chart2').html("<img class='loading' src='static/img/loading.gif'>");
        },
        success: function (data) {
            data = JSON.parse(data);
            data_list = []
            for (i = 0; i < data.length; i++) {
                name = data[i].name
                info = JSON.parse(data[i].data)
                data_list.push({
                    "name": name,
                    "data": info
                })
            }

            var new_chart2 = Highcharts.stockChart('chart2', {
                legend: {
                    enabled: true,
                    align: 'right',
                },

                rangeSelector: {
                    selected: 1
                },

                title: {
                    text: 'Instance CPU Utilities '
                },

                series: data_list
            });
        },
        error: function (xhr, textStatus, error) {
            $('#chart2').html("");
            show_alert("Unable to show the CPU Utilities chart ", "alert-danger")
            console.log(error)
        }
    });

    $.ajax({
        type: 'POST',
        url: '/fetch_requests_rate',
        data: JSON.stringify(instance),
        contentType: false,
        cache: false,
        processData: false,
        beforeSend: function () {
            $('#chart3').html("<img class='loading' src='static/img/loading.gif'>");
        },
        success: function (data) {
            data = JSON.parse(data);
            data_list = []
            for (i = 0; i < data.length; i++) {
                name = data[i].name
                info = JSON.parse(data[i].data)
                data_list.push({
                    "name": name,
                    "data": info
                })
            }

            var new_chart3 = Highcharts.stockChart('chart3', {
                legend: {
                    enabled: true,
                    align: 'right',
                },

                rangeSelector: {
                    selected: 1
                },

                title: {
                    text: 'Instance Requests rate '
                },

                series: data_list
            });
        },
        error: function (xhr, textStatus, error) {
            $('#charts3').html("");
            show_alert("Unable to show the Requests rate chart ", "alert-danger")
            console.log(error)
        }
    });
}

function add_instance() {
    $.ajax({
        type: 'POST',
        url: '/grow_one_worker',
        data: '',
        contentType: false,
        cache: false,
        processData: false,
        beforeSend: function () {
            $('#add_btn').html("Adding <img class='loader' src='static/img/loader.gif'>")
            $('#add_btn').prop("disabled", true)
            $('#shrink_btn').attr("disabled", true)
        },
        success: function (data) {
            data = JSON.parse(data);
            if (data.flag == true) {
                msg = 'One worker grown successfully.'
                show_alert(msg, 'alert-success')
                $('#worker_table').DataTable().ajax.reload();
            } else {
                show_alert(data.msg, 'alert-danger')
            }
            $('#add_btn').html("Add")
            $('#add_btn').prop("disabled", false)
            $('#shrink_btn').attr("disabled", false)
        },
        error: function (xhr, textStatus, error) {
            show_alert("Unable to grow a worker", "alert-danger")
            $('#add_btn').html("Add")
            $('#add_btn').prop("disabled", false)
            $('#shrink_btn').attr("disabled", false)
            console.log(error)
        }
    });
}

function delete_instance() {
    $.ajax({
        type: 'POST',
        url: '/shrink_one_worker',
        data: '',
        contentType: false,
        cache: false,
        processData: false,
        beforeSend: function () {
            $('#shrink_btn').html("Shrinking <img class='loader' src='static/img/loader.gif'>")
            $('#add_btn').prop("disabled", true)
            $('#shrink_btn').attr("disabled", true)
        },
        success: function (data) {
            data = JSON.parse(data);
            if (data.flag == true) {
                msg = "One worker deleted."
                show_alert(msg, 'alert-success')
                $('#worker_table').DataTable().ajax.reload();
            } else {
                show_alert(data.msg, 'alert-danger')
            }
            $('#shrink_btn').html("Delete")
            $('#add_btn').prop("disabled", false)
            $('#shrink_btn').attr("disabled", false)
        },
        error: function (xhr, textStatus, error) {
            show_alert("Unable to shrink a worker", "alert-danger")
            $('#shrink_btn').html("Delete")
            $('#add_btn').prop("disabled", false)
            $('#shrink_btn').attr("disabled", false)
            console.log(error)
        }
    });
}


function stop_manager() {
    msg = "manager stopped successfully!!!"
    show_alert(msg, 'alert-success')
    $.post('stop_manager_app', '');
}

function clear_data() {

    $.ajax({
        type: 'POST',
        url: '/clear_data',
        data: '',
        contentType: false,
        cache: false,
        processData: false,
        //beforeSend: function () {
        //    $('#delete_btn').html("Clearing <img class='loader' src='static/img/loader.gif'>")
        //    $('#delete_btn').prop("disabled", true)
        //},
        complete: function () {
            msg = 'All data deleted.'
            show_alert(msg, 'alert-success')

            $('#delete_btn').html("Delete All")
            $('#delete_btn').prop("disabled", false)
        },
        error: function (xhr, textStatus, error) {
            show_alert("Unable to delete data", "alert-danger")
            $('#delete_btn').html("Delete All")
            $('#delete_btn').prop("disabled", false)
            console.log(error)
        }
    });
}