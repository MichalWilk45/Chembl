package controllers

import javax.inject._
import play.api.mvc._
import play.api.libs.json._
import models.Category
import scala.collection.mutable.ListBuffer

@Singleton
class CategoryController @Inject()(cc: ControllerComponents) extends AbstractController(cc) {

  // Lista kategorii jako baza danych
  private val categories = ListBuffer(
    Category(1, "Elektronika"),
    Category(2, "Dom i Ogród")
  )

  def getAll: Action[AnyContent] = Action {
    Ok(Json.toJson(categories))
  }

  def getById(id: Int): Action[AnyContent] = Action {
    categories.find(_.id == id) match {
      case Some(category) => Ok(Json.toJson(category))
      case None => NotFound(Json.obj("error" -> "Category not found"))
    }
  }

  def add: Action[JsValue] = Action(parse.json) { request =>
    request.body.validate[Category] match {
      case JsSuccess(newCategory, _) =>
        categories += newCategory
        Created(Json.toJson(newCategory))
      case JsError(errors) =>
        BadRequest(Json.obj("error" -> "Invalid JSON", "details" -> JsError.toJson(errors)))
    }
  }

  def update(id: Int): Action[JsValue] = Action(parse.json) { request =>
    request.body.validate[Category] match {
      case JsSuccess(updatedCategory, _) =>
        categories.indexWhere(_.id == id) match {
          case -1 => NotFound(Json.obj("error" -> "Category not found"))
          case index =>
            categories.update(index, updatedCategory)
            Ok(Json.toJson(updatedCategory))
        }
      case JsError(errors) =>
        BadRequest(Json.obj("error" -> "Invalid JSON", "details" -> JsError.toJson(errors)))
    }
  }

  def delete(id: Int): Action[AnyContent] = Action {
    categories.indexWhere(_.id == id) match {
      case -1 => NotFound(Json.obj("error" -> "Category not found"))
      case index =>
        categories.remove(index)
        NoContent
    }
  }
}
