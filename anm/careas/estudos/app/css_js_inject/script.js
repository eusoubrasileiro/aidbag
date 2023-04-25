// to work on live-server vscode or chrome using a interferencia page downloaded
// add this bellow to testing page html
// <footer>  <!-- added by me for developing an injection tool -->    
// <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.6.4/jquery.min.js"></script>        
// <script src="script.js"></script>
// <link rel="stylesheet" href="style.css">  
// </footer> 

checked_dict = {}; // get dict of processes marked on database
var mainprocess;

function getmainprocess(){
    // Needs aidbag anm estudos work app running on localhost
    return $("table#ctl00_cphConteudo_gvLowerLeft tbody tr td:first-child")[0].innerText;
}

function highlight_checkboxes_prioridade(){

  console.log(`Process in analysis is ${mainprocess}`)
  mainprocess = getmainprocess();
  fetch(`http://127.0.0.1:5000/get_prioridade?process=${mainprocess}`)
  .then(res => res.json()
  .then( data => { 
    checked_dict = data
    $("table#ctl00_cphConteudo_gvLowerRight tbody tr td label[onclick='IdentificarProcesso(this);']").each(
      function(i, element) { 
          let process = element.innerText;
          console.log(`${process} is ${checked_dict[process]}`);
          element.style.fontWeight = 'bolder';
          element.style.fontStyle = 'oblique';
          if(checked_dict[process] == '0'){ // style to red the ones to uncheck
            element.style.color = 'red';
          }
      }
    );
    }))
    .catch((error) => {
      alert(`Erro no helper applet ${error}`);
    });  
}

$( document ).ready(function() {

  // navbar to count number of of checkboxes checked and unchecked
  const header_html = `
    <div class="navbarcontainer">
      <div class="navbar">
          <div class="navrow h1"> ${getmainprocess()} </div>
          <div class="navrow h2"> checkboxes <span id="count-checkboxes">0</span> </div> 
          <div class="navrow h2"> checked <span id="count-checked-checkboxes">0</span> </div>        
      </div>
    </div>
  `;
  document.querySelector("body").insertAdjacentHTML("afterbegin", header_html);  
  var $checkboxes = $("table#ctl00_cphConteudo_gvLowerRight tbody tr td input[type='checkbox']");
  var total = $checkboxes.length;
  $('#count-checkboxes').text(total);    
  $checkboxes.change(function(){
    let countCheckedCheckboxes = $checkboxes.filter(':checked').length;
    $('#count-checked-checkboxes').text(countCheckedCheckboxes);
  });

  highlight_checkboxes_prioridade();

  // adding callback to update on database when estudo is finished 9th and 10th tr on toolbar
  document.onmousedown = function (event) {
    if (!event) {event = window.event;}
    // console.info("mousedown  target is "+ event.target + " target parent is " + event.target.parentElement + " parent attributes");
    parent_id = event.target.parentElement.getAttribute("id")
    console.log("parent id attribute " + parent_id);
    if (parent_id == 'ctl00_cphConteudo_Toolbar1ExecutarEstudo' || 
        parent_id == 'ctl00_cphConteudo_Toolbar1GerarRelatorio' ||
        parent_id == 'ctl00_cphConteudo_Toolbar1FinalizarEstudo' )
      fetch(`http://127.0.0.1:5000/iestudo_finish?process=${mainprocess}`); // make database know this estudo is finished
  };

  // didn't load list of checkbox reload it on ENTER
  $(document).keypress(function(e) { 
    if(e.which == 13) {
      highlight_checkboxes_prioridade();
    }
  });

  // force refresh of checkboxes navbar
  $checkboxes.change();

});





