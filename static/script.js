$('#file-upload').change(function() {
    var filepath = this.value;
    var m = filepath.match(/([^\/\\]+)$/);
    var filename = m[1];
    $('#filename').text(filename);
});

function callDownCode()
{
    var datacode = document.getElementById("downloadcode").value
    var CallResolve = "/uploads/"+datacode
    window.open(CallResolve,"_blank")
}

