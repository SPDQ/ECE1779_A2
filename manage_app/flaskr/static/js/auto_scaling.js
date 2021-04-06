$(document).ready(function () {

    $("button[class~='btn-success']").each(function (i, btns) {
        // console.log(btns)
        $(btns).on("click", function (e) {
            e.preventDefault();
            modify_en($(btns).attr('id'));
        });
    });
});

function modify_en(id) {
    // console.log(id)
    if (id == "configure_btn_1") {
        $("#cpu_up").prop('readonly', false);
    } else if (id == "configure_btn_2") {
        $("#cpu_down").prop('readonly', false);
    } else if (id == "configure_btn_3") {
        $("#ratio_up").prop('readonly', false);
    } else if (id == "configure_btn_4") {
        $("#ratio_down").prop('readonly', false);
    } else { }
}


